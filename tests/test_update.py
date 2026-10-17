import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication

from conftest import wait
from matcontrol import runner, updates
from matcontrol.config import Config
from matcontrol.plugin_base import PluginContext
from matcontrol.plugins import update
from matcontrol.widgets import Tile

DNF_OUTPUT = """Upgrades
cargo.x86_64                      1.99.0-1.fc44   updates
google-chrome-stable.x86_64       155.0.8059.84-1 google-chrome
rust.x86_64                       1.99.0-1.fc44   updates

Obsoleting packages
old.x86_64                        1.0-1.fc44      updates
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def no_pkexec(monkeypatch):
    """Run the command as the current user instead of through pkexec."""
    monkeypatch.setattr(runner, "privileged_argv", lambda command: ["sh", "-c", command])


def make_plugin(tmp_path, monkeypatch, count=0):
    monkeypatch.setattr(updates, "check", lambda: updates.UpdateStatus(count=count))
    return update.UpdatePlugin(), PluginContext(Config(tmp_path / "c.json"), "update")


def test_parse_dnf_check_update_counts_upgrades_only():
    assert updates.parse_dnf_check_update(DNF_OUTPUT) == 3
    assert updates.parse_dnf_check_update("") == 0


def test_parse_flatpak_updates():
    assert updates.parse_flatpak_updates("com.a.App\norg.b.App\n\n") == 2


def test_clean_output_strips_ansi_and_redrawn_lines():
    lines = updates.clean_output("\x1b[1mhello\x1b[0m\nprogress 10%\rprogress 100%\npartial")
    assert lines == ["hello", "progress 100%", "partial"]


def fake_run(results):
    def run(argv, **kwargs):
        value = results[argv[0]]
        if isinstance(value, Exception):
            raise value
        return subprocess.CompletedProcess(argv, value[0], value[1], value[2])

    return run


def test_check_adds_dnf_and_flatpak(monkeypatch):
    monkeypatch.setattr(updates.subprocess, "run", fake_run({"dnf": (100, DNF_OUTPUT, ""), "flatpak": (0, "x.y\n", "")}))
    assert updates.check() == updates.UpdateStatus(count=4)


def test_check_without_updates(monkeypatch):
    monkeypatch.setattr(updates.subprocess, "run", fake_run({"dnf": (0, "", ""), "flatpak": (0, "", "")}))
    assert updates.check().count == 0


def test_check_reports_dnf_failure(monkeypatch):
    monkeypatch.setattr(updates.subprocess, "run", fake_run({"dnf": (1, "", "Fehler: kaputt\n"), "flatpak": (0, "", "")}))
    assert updates.check().error == "Fehler: kaputt"


def test_check_tolerates_missing_tools(monkeypatch):
    monkeypatch.setattr(updates.subprocess, "run", fake_run({"dnf": FileNotFoundError(), "flatpak": FileNotFoundError()}))
    assert updates.check() == updates.UpdateStatus(count=0)


def test_tile_attention_and_subtitle_follow_pending_updates(qapp, tmp_path, monkeypatch):
    plugin, ctx = make_plugin(tmp_path, monkeypatch, count=3)
    assert plugin.tile_active(ctx) is False  # also starts the first check
    wait(150)
    assert plugin.tile_attention(ctx) is True
    assert plugin.tile_subtitle(ctx) == "3 Updates verfügbar"


def test_tile_is_calm_when_up_to_date(qapp, tmp_path, monkeypatch):
    plugin, ctx = make_plugin(tmp_path, monkeypatch, count=0)
    plugin.tile_active(ctx)
    wait(150)
    assert plugin.tile_attention(ctx) is False
    assert plugin.tile_subtitle(ctx) == "System aktuell"


def test_update_runs_inverted_until_done(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch, count=2)
    ctx.settings["command"] = "echo hello; sleep 0.3; echo world 1>&2"
    plugin.tile_active(ctx)
    wait(150)
    plugin.toggle(ctx)
    assert plugin.tile_active(ctx) is True and plugin.tile_attention(ctx) is False
    assert plugin.tile_subtitle(ctx) == "Wird aktualisiert …"
    wait(900)
    assert plugin.tile_active(ctx) is False
    assert list(plugin.log)[0].startswith("$ echo hello")
    assert "hello" in plugin.log and "world" in plugin.log and plugin.log[-1] == "Fertig."


def test_failed_update_is_reported(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    ctx.settings["command"] = "exit 3"
    plugin.toggle(ctx)
    wait(500)
    assert plugin.tile_subtitle(ctx) == "Fehlgeschlagen (Code 3)"


def test_dismissed_polkit_dialog_is_reported_as_cancelled(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    ctx.settings["command"] = "exit 126"
    plugin.toggle(ctx)
    wait(500)
    assert plugin.tile_subtitle(ctx) == "Abgebrochen"


def test_second_start_is_ignored_while_running(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    ctx.settings["command"] = "echo run; sleep 0.3"
    plugin.toggle(ctx)
    plugin.toggle(ctx)
    wait(800)
    assert list(plugin.log).count("run") == 1


def test_missing_pkexec_does_not_hang(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "privileged_argv", lambda command: ["/nonexistent/pkexec", command])
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    plugin.toggle(ctx)
    wait(300)
    assert not plugin.running and "Fehlgeschlagen" in plugin.tile_subtitle(ctx)


def test_detail_page_saves_command_and_shows_log(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    page = plugin.create_widget(ctx)
    page.show()
    page.command.setText("echo page-run")
    page.start_button.click()
    wait(600)
    assert ctx.settings["command"] == "echo page-run"
    assert "page-run" in page.log_view.toPlainText()
    page.command.setText("")
    page._save_command()
    assert "command" not in ctx.settings


def test_tile_icon_tints_when_attention_and_inverts_when_active(qapp, tmp_path, monkeypatch):
    plugin, ctx = make_plugin(tmp_path, monkeypatch, count=2)
    plugin.tile_active(ctx)
    wait(150)
    tile = Tile(plugin, ctx)
    assert tile.icon_button.attention.target == 1.0 and tile.icon_button.tone.target == 0.0
    plugin._runner = runner.CommandRunner()
    plugin._runner._process = object()  # pretend an update is running
    tile.refresh()
    assert tile.icon_button.tone.target == 1.0 and tile.icon_button.attention.target == 0.0
    plugin._runner._process = None
