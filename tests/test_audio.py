import sys
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from conftest import wait
from matcontrol import audio_backend as audio
from matcontrol.config import Config
from matcontrol.plugin_base import PluginContext
from matcontrol.plugins import audiosplit
from matcontrol.widgets import Slider

A, B, C = "sink_a", "sink_b", "sink_c"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


class FakePulse:
    """Just enough of pulsectl.Pulse for audio_backend."""

    def __init__(self, default=A):
        self.default = default
        self.sinks = [self._sink(n, f"Device {n}") for n in (A, B, C)]
        self.modules = []
        self.volumes = {}

    @staticmethod
    def _sink(name, description, volume=1.0):
        return SimpleNamespace(name=name, description=description, volume=SimpleNamespace(value_flat=volume), mute=0)

    def __call__(self, _client_name):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sink_list(self):
        return list(self.sinks)

    def server_info(self):
        return SimpleNamespace(default_sink_name=self.default)

    def module_list(self):
        return list(self.modules)

    def module_load(self, name, args):
        self.modules.append(SimpleNamespace(index=len(self.modules) + 1, name=name, argument=args))
        self.sinks.append(self._sink(audio.SINK_NAME, audio.DESCRIPTION))

    def module_unload(self, index):
        self.modules = [m for m in self.modules if m.index != index]
        self.sinks = [s for s in self.sinks if s.name != audio.SINK_NAME]

    def sink_default_set(self, name):
        self.default = name

    def get_sink_by_name(self, name):
        return next(s for s in self.sinks if s.name == name)

    def volume_set_all_chans(self, sink, value):
        self.volumes[sink.name] = value


@pytest.fixture
def pulse(monkeypatch):
    fake = FakePulse()
    monkeypatch.setattr(audio.pulsectl, "Pulse", fake)
    return fake


def test_snapshot_hides_the_combined_output(pulse):
    audio.enable([A, B])
    snap = audio.snapshot()
    assert snap.active and [d.name for d in snap.devices] == [A, B, C]


def test_enable_combines_selected_and_returns_previous_default(pulse):
    previous = audio.enable([B, C])
    assert previous == A and pulse.default == audio.SINK_NAME
    assert f"slaves={B},{C}" in pulse.modules[0].argument


def test_enable_twice_rebuilds_and_keeps_no_previous(pulse):
    audio.enable([A, B])
    assert audio.enable([A, C]) is None
    assert len(pulse.modules) == 1 and f"slaves={A},{C}" in pulse.modules[0].argument


def test_disable_restores_default_and_removes_module(pulse):
    previous = audio.enable([A, B])
    audio.disable(previous)
    assert pulse.default == A and not pulse.modules and not audio.snapshot().active


def test_set_volume_is_clamped(pulse):
    audio.set_volume(A, 1.7)
    audio.set_volume(B, -1)
    assert pulse.volumes == {A: 1.0, B: 0.0}


def test_enable_without_devices_is_an_error(pulse):
    with pytest.raises(audio.AudioError):
        audio.enable([])


def test_unreachable_server_becomes_audio_error(monkeypatch):
    def broken(_name):
        raise audio.pulsectl.PulseError("no server")

    monkeypatch.setattr(audio.pulsectl, "Pulse", broken)
    with pytest.raises(audio.AudioError):
        audio.snapshot()


def make_plugin(tmp_path):
    return audiosplit.AudioSplitPlugin(), PluginContext(Config(tmp_path / "c.json"), "audiosplit")


def test_plugin_needs_two_devices_before_it_switches_on(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    plugin.tile_active(ctx)
    wait(150)
    plugin.set_selected(ctx, A, True)
    plugin.toggle(ctx)
    wait(150)
    assert not pulse.modules
    assert plugin.tile_subtitle(ctx) == "2 Geräte wählen"


def test_plugin_toggle_on_and_off(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    plugin.tile_active(ctx)
    wait(150)
    plugin.set_selected(ctx, A, True)
    plugin.set_selected(ctx, B, True)
    plugin.toggle(ctx)
    assert plugin.tile_active(ctx) is True  # optimistic while the worker runs
    wait(300)
    assert pulse.default == audio.SINK_NAME and plugin.snapshot.active
    assert plugin.tile_subtitle(ctx) == "Aktiv auf 2 Geräten"
    assert ctx.settings["previous_default"] == A
    plugin.toggle(ctx)
    wait(300)
    assert pulse.default == A and not plugin.snapshot.active


def test_changing_selection_while_active_rebuilds(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    plugin.tile_active(ctx)
    wait(150)
    plugin.set_selected(ctx, A, True)
    plugin.set_selected(ctx, B, True)
    plugin.toggle(ctx)
    wait(300)
    plugin.set_selected(ctx, C, True)
    wait(300)
    assert f"slaves={A},{B},{C}" in pulse.modules[0].argument
    plugin.set_selected(ctx, A, False)
    plugin.set_selected(ctx, B, False)
    plugin.set_selected(ctx, C, False)
    wait(500)
    assert not pulse.modules and pulse.default == A


def test_detail_page_lists_devices_and_sets_volume(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    page = plugin.create_widget(ctx)
    page.show()
    wait(200)
    assert list(page.rows) == [A, B, C]
    page.rows[A].slider.user_changed.emit(40)
    wait(300)
    assert pulse.volumes[A] == pytest.approx(0.4)


def test_slider_click_sets_value_and_emits(qapp):
    slider = Slider()
    slider.resize(209, 26)
    slider.show()
    seen = []
    slider.user_changed.connect(seen.append)
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(104, 13))
    assert 45 <= slider.value() <= 55 and seen
    slider.setValue(20)  # programmatic: no user_changed
    assert len(seen) == 1
