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
    reset = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    start = reset - timedelta(days=7)
    assert usage.pace_target(reset, start) == pytest.approx(100 / 7)  # first day
    assert usage.pace_target(reset, start + timedelta(days=3, hours=5)) == pytest.approx(400 / 7)  # fourth day
    assert usage.pace_target(reset, reset - timedelta(seconds=1)) == pytest.approx(100.0)  # seventh day
    assert usage.pace_target(reset, reset + timedelta(hours=1)) == 100.0
    assert usage.pace_target(None) is None


def test_tile_sits_under_system_tile():
    plugins, errors = discover()
    placed = place_tiles(plugins)
    assert not errors and placed["system"] == (0, 2) and placed["usage"] == (2, 2)


def make_ctx(tmp_path):
    from matcontrol.config import Config
    from matcontrol.plugin_base import PluginContext

    return PluginContext(Config(tmp_path / "c.json"), "usage")


def test_format_reset():
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert usage.format_reset(now + timedelta(days=2, hours=3, minutes=5), now) == "Reset in 2d 3h"
    assert usage.format_reset(now + timedelta(hours=5, minutes=7), now) == "Reset in 5h 7m"
    assert usage.format_reset(now - timedelta(seconds=1), now) == "Reset jetzt"
    assert usage.format_reset(None) == ""


def test_tile_shows_reset_and_target_marker(qapp, tmp_path):
    tile = usage_plugin.UsageTile(make_ctx(tmp_path))
    resets = datetime.now(timezone.utc) + timedelta(days=3, hours=1)
    tile._fetched(usage.WeeklyUsage(42.0, resets), None)
    assert tile.row.right.text() == "42 %" and tile.row.left.text().startswith("Reset in 3d")
    assert tile.row.meter.has_marker and tile.row.meter.marker.target == pytest.approx(4 / 7)


def test_tile_keeps_last_value_when_fetch_fails_and_after_restart(qapp, tmp_path):
    ctx = make_ctx(tmp_path)
    tile = usage_plugin.UsageTile(ctx)
    tile._fetched(None, usage.UsageError("Token abgelaufen, Claude Code starten"))
    assert tile.row.right.text() == "Token abgelaufen, Claude Code starten"
    tile._fetched(usage.WeeklyUsage(42.0, datetime.now(timezone.utc) + timedelta(days=2)), None)
    tile._fetched(None, usage.UsageError("Keine Verbindung"))
    assert tile.row.right.text() == "42 %" and tile.row.left.text().endswith("(alt)")
    restarted = usage_plugin.UsageTile(ctx)  # new app start, still no connection
    restarted.render()
    assert restarted.row.right.text() == "42 %"


def test_tile_ignores_saved_value_of_a_past_week(qapp, tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.settings["last"] = {"percent": 90.0, "resets_at": "2020-01-01T00:00:00+00:00"}
    assert usage_plugin.UsageTile(ctx).usage is None


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
