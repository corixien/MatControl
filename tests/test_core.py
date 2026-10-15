import importlib
import sys

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from matcontrol.config import Config
from matcontrol.plugin_base import Plugin
from matcontrol.plugin_loader import discover
from matcontrol.window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


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


def test_discover_skips_underscore_files_and_never_raises():
    plugins, errors = discover()
    assert all(p.id != "example" for p in plugins)
    assert errors == []


def test_discover_reports_broken_plugin(tmp_path, monkeypatch):
    import matcontrol.plugins as pkg

    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.setattr(pkg, "__path__", [str(tmp_path)])
    plugins, errors = discover()
    assert plugins == []
    assert len(errors) == 1 and "boom" in errors[0]


def test_window_builds_a_page_per_plugin(qapp, tmp_path):
    class Dummy(Plugin):
        id = "dummy"
        name = "Dummy"

        def create_widget(self, ctx):
            return QWidget()

    window = MainWindow(Config(tmp_path / "c.json"), [Dummy()], [])
    assert window.stack.count() == 1
    assert window.sidebar.count() == 1
