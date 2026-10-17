import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication

from conftest import wait
from matcontrol import network, runner
from matcontrol.config import Config
from matcontrol.plugin_base import PluginContext
from matcontrol.plugins import network as network_plugin


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def no_pkexec(monkeypatch):
    monkeypatch.setattr(runner, "privileged_argv", lambda command: ["sh", "-c", command])


def make_plugin(tmp_path, monkeypatch, state="connected"):
    monkeypatch.setattr(network, "current_state", lambda: state)
    return network_plugin.NetworkPlugin(), PluginContext(Config(tmp_path / "c.json"), "network")


def test_describe_state():
    assert network.describe_state("connected\n") == "Verbunden"
    assert network.describe_state("connected (site only)") == "Verbunden"
    assert network.describe_state("disconnected") == "Getrennt"
    assert network.describe_state("connecting") == "Verbindet …"
    assert network.describe_state("") == "Unbekannt"
    assert network.describe_state("weird") == "Weird"


def test_current_state_parses_nmcli(monkeypatch):
    monkeypatch.setattr(
        network.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "connected\n", "")
    )
    assert network.current_state() == "connected"


def test_current_state_raises_when_nmcli_fails(monkeypatch):
    monkeypatch.setattr(
        network.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 8, "", "NetworkManager is not running.\n")
    )
    with pytest.raises(RuntimeError, match="not running"):
        network.current_state()


def test_command_starts_even_if_stop_fails():
    assert network_plugin.COMMAND == "systemctl stop NetworkManager; systemctl start NetworkManager"


def test_tile_shows_connection_state(qapp, tmp_path, monkeypatch):
    plugin, ctx = make_plugin(tmp_path, monkeypatch, state="disconnected")
    assert plugin.tile_active(ctx) is False
    wait(150)
    assert plugin.tile_subtitle(ctx) == "Getrennt"


def test_tile_reports_unreachable_network_manager(qapp, tmp_path, monkeypatch):
    def broken():
        raise RuntimeError("weg")

    monkeypatch.setattr(network, "current_state", broken)
    plugin, ctx = network_plugin.NetworkPlugin(), PluginContext(Config(tmp_path / "c.json"), "network")
    plugin.tile_active(ctx)
    wait(150)
    assert plugin.tile_subtitle(ctx) == "NetworkManager nicht erreichbar"


def test_restart_is_active_until_the_commands_finish(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    monkeypatch.setattr(network_plugin, "COMMAND", "echo stopping; sleep 0.3; echo starting")
    plugin.tile_active(ctx)
    wait(150)
    plugin.toggle(ctx)
    assert plugin.tile_active(ctx) is True
    assert plugin.tile_subtitle(ctx) == "Wird neu gestartet …"
    wait(900)
    assert plugin.tile_active(ctx) is False
    assert "stopping" in plugin.log and "starting" in plugin.log and plugin.log[-1] == "Fertig."
    assert plugin.tile_subtitle(ctx) == "Verbunden"


def test_second_restart_is_ignored_while_running(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    monkeypatch.setattr(network_plugin, "COMMAND", "echo once; sleep 0.3")
    plugin.toggle(ctx)
    plugin.toggle(ctx)
    wait(800)
    assert list(plugin.log).count("once") == 1


def test_failed_restart_and_cancelled_dialog(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    monkeypatch.setattr(network_plugin, "COMMAND", "exit 4")
    plugin.toggle(ctx)
    wait(500)
    assert plugin.tile_subtitle(ctx) == "Fehlgeschlagen (Code 4)"
    monkeypatch.setattr(network_plugin, "COMMAND", "exit 126")
    plugin.toggle(ctx)
    wait(500)
    assert plugin.tile_subtitle(ctx) == "Abgebrochen"


def test_successful_restart_clears_an_earlier_error(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    plugin.last_result = "Fehlgeschlagen (Code 4)"
    monkeypatch.setattr(network_plugin, "COMMAND", "true")
    plugin.toggle(ctx)
    wait(500)
    assert plugin.last_result is None


def test_detail_page_button_restarts_and_shows_log(qapp, tmp_path, monkeypatch, no_pkexec):
    plugin, ctx = make_plugin(tmp_path, monkeypatch)
    monkeypatch.setattr(network_plugin, "COMMAND", "echo from-page")
    page = plugin.create_widget(ctx)
    page.show()
    page.button.click()
    wait(500)
    assert "from-page" in page.log_view.toPlainText()
    assert page.button.isEnabled()
