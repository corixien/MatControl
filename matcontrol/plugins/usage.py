"""Claude usage: 2x1 tile with the weekly limit used so far (claude.ai + Claude Code) with a line at the daily target. A click opens Claude Desktop, or starts the sign-in when logged out."""

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..plugin_base import Plugin, PluginContext
from ..tasks import run_in_thread
from ..usage import UsageError, WeeklyUsage, fetch_weekly_usage, format_reset, pace_target
from .system import MetricRow

REFRESH_S = 300  # the endpoint is undocumented and rate limited: ask rarely
RETRY_S = 30  # after a failure that may fix itself (offline, logged in again, token renewed)
CHECK_MS = 30_000
FIRST_CHECK_MS = 200
DESKTOP_APPS = ("claude-desktop",)
TERMINALS = ("konsole", "gnome-terminal", "xterm")
LOGIN_ARGS = ["auth", "login"]


def find_desktop_app() -> str | None:
    for name in DESKTOP_APPS:
        path = shutil.which(name)
        if path:
            return path
    return None


def find_claude() -> str | None:
    return shutil.which("claude") or (str(p) if (p := Path.home() / ".local" / "bin" / "claude").exists() else None)


def start_login() -> bool:
    """`claude auth login` in a terminal window: it opens the browser and asks for the code if needed."""
    claude = find_claude()
    for name in TERMINALS:
        terminal = shutil.which(name)
        if claude and terminal:
            return QProcess.startDetached(terminal, ["-e", claude, *LOGIN_ARGS])
    return False


class UsageTile(QWidget):
    """Fetches in a worker thread, only while visible and at most every REFRESH_S seconds.
    The last value is kept in the settings: Claude Code renews its token only when it is used, so
    after a day without it the fetch fails and the tile shows the last known value as "alt"."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.usage: WeeklyUsage | None = self._load()
        self.error: str | None = None
        self.hint = ""
        self.needs_login = False
        self._fetched_at = 0.0
        self._interval = REFRESH_S
        self._fetching = False
        self.row = MetricRow("Claude Woche", dim_left=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(self.row)
        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(CHECK_MS)
        self.timer.timeout.connect(self.refresh)

    def _load(self) -> WeeklyUsage | None:
        saved = self.ctx.settings.get("last")
        try:
            usage = WeeklyUsage(float(saved["percent"]), datetime.fromisoformat(saved["resets_at"]))
        except (TypeError, KeyError, ValueError):
            return None
        return usage if usage.resets_at > datetime.now(timezone.utc) else None  # last week's value is useless

    def _save(self, usage: WeeklyUsage) -> None:
        if usage.resets_at is not None:
            self.ctx.settings["last"] = {"percent": usage.percent, "resets_at": usage.resets_at.isoformat()}
            self.ctx.save()

    def showEvent(self, event) -> None:
        self.timer.start()
        QTimer.singleShot(FIRST_CHECK_MS, self.refresh)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        if self._fetching or not self.isVisible() or time.monotonic() - self._fetched_at < self._interval:
            self.render()
            return
        self._fetching = True
        run_in_thread(fetch_weekly_usage, self._fetched)

    def _fetched(self, usage: WeeklyUsage | None, error: Exception | None) -> None:
        self._fetching = False
        self._fetched_at = time.monotonic()
        if error is None:
            self.usage, self.error, self.hint, self._interval = usage, None, "", REFRESH_S
            self.needs_login = False
            self._save(usage)
        else:
            known = isinstance(error, UsageError)
            self.error = error.short if known else "Fehler"
            self.hint = error.hint if known else str(error)
            self.needs_login = known and error.login
            self._interval = REFRESH_S if not known or error.slow else RETRY_S
        self.render()

    def render(self) -> None:
        self.setToolTip(self.hint if self.error else "")
        if self.usage is None:
            self.row.show_value(self.error or "–", 0.0, left="Claude Woche")
            return
        now = datetime.now(timezone.utc)
        left = format_reset(self.usage.resets_at, now) or "Claude Woche"
        if self.error:
            left += " (alt)"
        target = pace_target(self.usage.resets_at, now)
        self.row.show_value(
            f"{self.usage.percent:.0f} %",
            self.usage.percent / 100,
            left=left,
            marker=None if target is None else target / 100,
        )


class UsagePlugin(Plugin):
    id = "usage"
    name = "Claude Nutzung"
    order = 40  # after the other 2x1 tiles: flows into the cell under the System tile
    has_detail = False

    tile: UsageTile | None = None

    def create_tile(self, ctx: PluginContext) -> QWidget:
        self.tile = UsageTile(ctx)
        return self.tile

    def tile_clicked(self, ctx: PluginContext) -> None:
        if self.tile is not None and self.tile.needs_login:
            started = start_login()
        else:
            app = find_desktop_app()
            started = bool(app) and QProcess.startDetached(app, [])
        if started:
            ctx.request_close()

    def create_widget(self, ctx: PluginContext) -> QWidget:
        raise NotImplementedError  # has_detail is False


PLUGIN = UsagePlugin()
