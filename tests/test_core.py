import importlib
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from matcontrol.config import Config
from matcontrol.plugin_base import Plugin, PluginContext
from matcontrol.plugin_loader import discover
from matcontrol.widgets import DetailPage, Tile
from matcontrol.window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


class Toggler(Plugin):
    id = "toggler"
    name = "Toggler"

    def tile_active(self, ctx):
        return ctx.settings.get("on", False)

    def tile_subtitle(self, ctx):
        return "An" if ctx.settings.get("on") else "Aus"

    def toggle(self, ctx):
        ctx.settings["on"] = not ctx.settings.get("on", False)

    def create_widget(self, ctx):
        return QWidget()


class Plain(Plugin):
    id = "plain"
    name = "Plain"

    def create_widget(self, ctx):
        return QWidget()


def make_ctx(tmp_path, plugin_id):
    return PluginContext(Config(tmp_path / "c.json"), plugin_id)


def test_config_roundtrip(tmp_path):
    cfg = Config(tmp_path / "c.json")
    cfg.plugin("x")["a"] = 1
    cfg.save()
    assert Config(tmp_path / "c.json").plugin("x") == {"a": 1}


def test_config_corrupt_file_is_empty(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{broken", encoding="utf-8")
    assert Config(path).plugin("x") == {}


def test_example_template_is_a_valid_plugin():
    module = importlib.import_module("matcontrol.plugins._example")
    assert isinstance(module.PLUGIN, Plugin)
    assert module.PLUGIN.toggleable


def test_discover_skips_underscore_files_and_never_raises(monkeypatch):
    monkeypatch.delenv("MATCONTROL_LOAD_EXAMPLE", raising=False)
    plugins, errors = discover()
    assert all(p.id != "example" for p in plugins)
    assert errors == []


def test_discover_loads_example_on_request(monkeypatch):
    monkeypatch.setenv("MATCONTROL_LOAD_EXAMPLE", "1")
    plugins, errors = discover()
    assert [p.id for p in plugins if p.id == "example"] == ["example"]
    assert errors == []


def test_discover_reports_broken_plugin(tmp_path, monkeypatch):
    import matcontrol.plugins as pkg

    monkeypatch.delenv("MATCONTROL_LOAD_EXAMPLE", raising=False)
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.setattr(pkg, "__path__", [str(tmp_path)])
    plugins, errors = discover()
    assert plugins == []
    assert len(errors) == 1 and "boom" in errors[0]


def test_toggleable_detection():
    assert Toggler().toggleable
    assert not Plain().toggleable


def test_tile_icon_click_toggles_and_recolors(qapp, tmp_path):
    plugin, ctx = Toggler(), make_ctx(tmp_path, "toggler")
    tile = Tile(plugin, ctx)
    assert tile.property("state") == "off" and tile.subtitle.text() == "Aus"
    tile.icon_button.click()
    assert tile.property("state") == "on" and tile.subtitle.text() == "An"


def test_tile_without_state_is_neutral_and_icon_opens_details(qapp, tmp_path):
    tile = Tile(Plain(), make_ctx(tmp_path, "plain"))
    opened = []
    tile.opened.connect(lambda: opened.append(1))
    assert tile.property("state") == "none"
    tile.icon_button.click()
    assert opened == [1]


def test_tile_body_click_opens_details_without_toggling(qapp, tmp_path):
    plugin, ctx = Toggler(), make_ctx(tmp_path, "toggler")
    tile = Tile(plugin, ctx)
    tile.show()
    opened = []
    tile.opened.connect(lambda: opened.append(1))
    QTest.mouseClick(tile, Qt.MouseButton.LeftButton)
    assert opened == [1]
    assert ctx.settings.get("on", False) is False


def test_detail_switch_follows_state(qapp, tmp_path):
    plugin, ctx = Toggler(), make_ctx(tmp_path, "toggler")
    page = DetailPage(plugin, ctx)
    assert page.switch is not None and not page.switch.isChecked()
    page.switch.click()
    assert ctx.settings["on"] is True and page.switch.isChecked()
    assert DetailPage(Plain(), make_ctx(tmp_path, "plain")).switch is None


def test_window_home_navigation(qapp, tmp_path):
    window = MainWindow(Config(tmp_path / "c.json"), [Toggler(), Plain()], [], popup=False)
    assert window.stack.count() == 3  # home + one detail page per plugin
    window.open_plugin("plain")
    assert window.stack.currentWidget() is window.pages["plain"]
    window.pages["plain"].back.emit()
    assert window.stack.currentIndex() == 0


def test_popup_slides_in_and_out(qapp, tmp_path):
    window = MainWindow(Config(tmp_path / "c.json"), [Toggler()], [], popup=True)
    window.show_animated()
    QTest.qWait(400)
    assert window.panel.pos().y() == 0
    window.hide_animated()
    QTest.qWait(400)
    assert not window.isVisible()
