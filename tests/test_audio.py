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
        self.next_index = 0

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
        self.next_index += 1
        self.modules.append(SimpleNamespace(index=self.next_index, name=name, argument=args))
        if name in (audio.NULL_MODULE, audio.LEGACY_COMBINE_MODULE):
            self.sinks.append(self._sink(audio.SINK_NAME, audio.DESCRIPTION))
        return self.next_index

    def module_unload(self, index):
        gone = next(m for m in self.modules if m.index == index)
        self.modules = [m for m in self.modules if m.index != index]
        if gone.name in (audio.NULL_MODULE, audio.LEGACY_COMBINE_MODULE):
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


def loopbacks(pulse):
    return [m for m in pulse.modules if m.name == audio.LOOPBACK_MODULE]


def latency_of(module):
    return int(module.argument.split("latency_msec=")[1].split()[0])


def test_snapshot_hides_the_virtual_output(pulse):
    audio.enable({A: 0, B: 0})
    snap = audio.snapshot()
    assert snap.active and [d.name for d in snap.devices] == [A, B, C]


def test_enable_builds_null_sink_and_a_loopback_per_device(pulse):
    previous = audio.enable({B: 0, C: 120})
    assert previous == A and pulse.default == audio.SINK_NAME
    assert [m.name for m in pulse.modules][0] == audio.NULL_MODULE
    by_device = {m.argument.split("sink=")[1].split()[0]: latency_of(m) for m in loopbacks(pulse)}
    assert by_device == {B: audio.BASE_LATENCY_MS, C: audio.BASE_LATENCY_MS + 120}
    assert all(f"source={audio.SINK_NAME}.monitor" in m.argument for m in loopbacks(pulse))


def test_delay_is_clamped(pulse):
    audio.enable({A: 99999, B: -5})
    assert sorted(latency_of(m) for m in loopbacks(pulse)) == [
        audio.BASE_LATENCY_MS,
        audio.BASE_LATENCY_MS + audio.MAX_DELAY_MS,
    ]


def test_enable_twice_rebuilds_and_keeps_no_previous(pulse):
    audio.enable({A: 0, B: 0})
    assert audio.enable({A: 0, C: 0}) is None
    assert len(loopbacks(pulse)) == 2 and sum(m.name == audio.NULL_MODULE for m in pulse.modules) == 1


def test_enable_replaces_a_legacy_combine_sink(pulse):
    pulse.module_load(audio.LEGACY_COMBINE_MODULE, f"sink_name={audio.SINK_NAME} slaves={A},{B}")
    audio.enable({A: 0, B: 0})
    assert not [m for m in pulse.modules if m.name == audio.LEGACY_COMBINE_MODULE]


def test_set_delay_reloads_only_that_device(pulse):
    audio.enable({A: 0, B: 0})
    untouched = next(m for m in loopbacks(pulse) if f"sink={A} " in m.argument)
    audio.set_delay(B, 200)
    by_device = {m.argument.split("sink=")[1].split()[0]: latency_of(m) for m in loopbacks(pulse)}
    assert by_device == {A: audio.BASE_LATENCY_MS, B: audio.BASE_LATENCY_MS + 200}
    assert untouched in pulse.modules


def test_set_delay_does_nothing_while_split_is_off(pulse):
    audio.set_delay(A, 100)
    assert not pulse.modules


def test_disable_restores_default_and_removes_everything(pulse):
    previous = audio.enable({A: 0, B: 50})
    audio.disable(previous)
    assert pulse.default == A and not pulse.modules and not audio.snapshot().active


def test_set_volume_is_clamped(pulse):
    audio.set_volume(A, 1.7)
    audio.set_volume(B, -1)
    assert pulse.volumes == {A: 1.0, B: 0.0}


def test_enable_without_devices_is_an_error(pulse):
    with pytest.raises(audio.AudioError):
        audio.enable({})


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
    assert len(loopbacks(pulse)) == 3
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


def test_plugin_delay_is_stored_and_used_when_switching_on(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    plugin.tile_active(ctx)
    wait(150)
    plugin.set_selected(ctx, A, True)
    plugin.set_selected(ctx, B, True)
    plugin.set_delay(ctx, B, 140)
    plugin.toggle(ctx)
    wait(300)
    by_device = {m.argument.split("sink=")[1].split()[0]: latency_of(m) for m in loopbacks(pulse)}
    assert by_device == {A: audio.BASE_LATENCY_MS, B: audio.BASE_LATENCY_MS + 140}


def test_plugin_delay_change_applies_live(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    plugin.tile_active(ctx)
    wait(150)
    plugin.set_selected(ctx, A, True)
    plugin.set_selected(ctx, B, True)
    plugin.toggle(ctx)
    wait(300)
    plugin.set_delay(ctx, A, 80)
    wait(300)
    by_device = {m.argument.split("sink=")[1].split()[0]: latency_of(m) for m in loopbacks(pulse)}
    assert by_device[A] == audio.BASE_LATENCY_MS + 80
    assert ctx.settings["delays"][A] == 80


def test_delay_slider_applies_after_it_settles(qapp, pulse, tmp_path):
    plugin, ctx = make_plugin(tmp_path)
    page = plugin.create_widget(ctx)
    page.show()
    wait(200)
    page.rows[A].delay_slider.user_changed.emit(30)
    page.rows[A].delay_slider.user_changed.emit(45)
    assert "delays" not in ctx.settings  # debounced
    wait(500)
    assert ctx.settings["delays"][A] == 45


def test_slider_respects_range_and_step(qapp):
    slider = Slider()
    slider.setRange(0, 600)
    slider.setSingleStep(5)
    slider.resize(209, 26)
    slider.show()
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(104, 13))
    assert slider.value() % 5 == 0 and 270 <= slider.value() <= 330
