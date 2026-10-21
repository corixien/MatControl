import json
import sys
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QApplication

from matcontrol import usage
from matcontrol.plugins import usage as usage_plugin
from matcontrol.plugin_loader import discover
from matcontrol.window import place_tiles


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_parse_usage():
    result = usage.parse_usage({"seven_day": {"utilization": 49.0, "resets_at": "2026-10-24T10:00:00.000000+00:00"}})
    assert result.percent == 49.0 and result.resets_at.day == 24
    assert usage.parse_usage({"seven_day": {"utilization": 150, "resets_at": None}}).percent == 100.0
    with pytest.raises(usage.UsageError):
        usage.parse_usage({"five_hour": {}})


def test_read_token(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"claudeAiOauth": {"accessToken": "t", "expiresAt": 2_000_000_000_000}}))
    assert usage.read_token(path, now=1.0) == "t"
    with pytest.raises(usage.UsageError, match="abgelaufen"):
        usage.read_token(path, now=3_000_000_000)
    with pytest.raises(usage.UsageError, match="angemeldet"):
        usage.read_token(tmp_path / "missing.json")


def test_pace_target():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert usage.pace_target(now + timedelta(days=7), now) == pytest.approx(0.0)
    assert usage.pace_target(now + timedelta(days=6), now) == pytest.approx(100 / 7)
    assert usage.pace_target(now + timedelta(days=3.5), now) == pytest.approx(50.0)
    assert usage.pace_target(now - timedelta(seconds=1), now) == 100.0
    assert usage.pace_target(None) is None


def test_tile_sits_under_system_tile():
    plugins, errors = discover()
    placed = place_tiles(plugins)
    assert not errors and placed["system"] == (0, 2) and placed["usage"] == (2, 2)


def test_tile_shows_values_and_errors(qapp):
    tile = usage_plugin.UsageTile()
    tile._fetched(usage.WeeklyUsage(42.0, None), None)
    assert tile.row.right.text() == "42 %"
    tile._fetched(None, usage.UsageError("Keine Verbindung"))
    assert tile.row.right.text() == "42 %"  # the last good value stays
    fresh = usage_plugin.UsageTile()
    fresh._fetched(None, usage.UsageError("Keine Verbindung"))
    assert fresh.row.right.text() == "Keine Verbindung"


def test_click_launches_desktop_app(qapp, tmp_path, monkeypatch):
    from matcontrol.config import Config
    from matcontrol.plugin_base import PluginContext

    launched = []
    monkeypatch.setattr(usage_plugin, "find_desktop_app", lambda: "/usr/bin/claude-desktop")
    monkeypatch.setattr(usage_plugin.QProcess, "startDetached", lambda program, args: launched.append(program) or True)
    ctx = PluginContext(Config(tmp_path / "c.json"), "usage")
    closed = []
    ctx.close_requested.connect(lambda: closed.append(1))
    usage_plugin.PLUGIN.tile_clicked(ctx)
    assert launched == ["/usr/bin/claude-desktop"] and closed
