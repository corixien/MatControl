"""Claude usage: 2x1 tile with the weekly limit used so far (claude.ai + Claude Code). A click opens Claude Desktop."""

import shutil
import time
from datetime import datetime, timezone

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..plugin_base import Plugin, PluginContext
from ..tasks import run_in_thread
from ..usage import UsageError, WeeklyUsage, fetch_weekly_usage, pace_target
from .system import MetricRow

REFRESH_S = 300  # the endpoint is undocumented and rate limited: ask rarely
CHECK_MS = 30_000
FIRST_CHECK_MS = 200
DESKTOP_APPS = ("claude-desktop",)


def find_desktop_app() -> str | None:
    for name in DESKTOP_APPS:
        path = shutil.which(name)
        if path:
            return path
    return None


class UsageTile(QWidget):
    """Fetches in a worker thread, only while visible and at most every REFRESH_S seconds."""

    def __init__(self) -> None:
        super().__init__()
        self.usage: WeeklyUsage | None = None
        self.error: str | None = None
        self._fetched_at = 0.0
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

    def showEvent(self, event) -> None:
        self.timer.start()
        QTimer.singleShot(FIRST_CHECK_MS, self.refresh)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        if self._fetching or not self.isVisible() or time.monotonic() - self._fetched_at < REFRESH_S:
            self.render()
            return
        self._fetching = True
        run_in_thread(fetch_weekly_usage, self._fetched)

    def _fetched(self, usage: WeeklyUsage | None, error: Exception | None) -> None:
        self._fetching = False
        self._fetched_at = time.monotonic()
        if error is None:
            self.usage, self.error = usage, None
        else:
            self.error = str(error) if isinstance(error, UsageError) else "Fehler"
        self.render()

    def render(self) -> None:
        if self.error and self.usage is None:
            self.row.show_value(self.error, 0.0, left="Claude Woche")
        elif self.usage is not None:
            suffix = format_reset(self.usage.resets_at, datetime.now(timezone.utc))
            self.row.show_value(f"{self.usage.percent:.0f} %", self.usage.percent / 100, left=suffix or "Claude Woche")


class UsagePlugin(Plugin):
    id = "usage"
    name = "Claude Nutzung"
    order = 40  # after the other 2x1 tiles: flows into the cell under the System tile
    has_detail = False

    def create_tile(self, ctx: PluginContext) -> QWidget:
        return UsageTile()

    def tile_clicked(self, ctx: PluginContext) -> None:
        app = find_desktop_app()
        if app and QProcess.startDetached(app, []):
            ctx.request_close()

    def create_widget(self, ctx: PluginContext) -> QWidget:
        raise NotImplementedError  # has_detail is False


PLUGIN = UsagePlugin()
