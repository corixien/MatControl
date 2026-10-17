"""Network: restart NetworkManager (stop, then start), e.g. after plugging in an LTE stick.

Tile: the icon inverts while the restart runs; the status line shows the connection state.
Clicking the icon (or the switch on the detail page) restarts. Runs through pkexec (Polkit dialog).
"""

import time
from collections import deque

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from .. import network, theme
from ..plugin_base import Plugin, PluginContext
from ..runner import POLKIT_DISMISSED, CommandRunner
from ..tasks import run_in_thread
from ..widgets import Button

# `;` not `&&`: the start must run even when the stop reports an error, or the network stays down.
COMMAND = "systemctl stop NetworkManager; systemctl start NetworkManager"
STATE_STALE_S = 10.0
RECHECK_DELAY_MS = 3000  # NetworkManager needs a moment to bring the connection back
LOG_LINES = 200


class NetworkPlugin(Plugin):
    id = "network"
    name = "Netzwerk"
    icon = "network-wired"
    order = 30

    def __init__(self) -> None:
        self.state: str | None = None  # raw nmcli state
        self.state_error: str | None = None
        self.last_result: str | None = None  # "Abgebrochen" / "Fehlgeschlagen (Code N)" until the next restart
        self.log: deque[str] = deque(maxlen=LOG_LINES)
        self._runner: CommandRunner | None = None
        self._ctx: PluginContext | None = None
        self._state_at = 0.0
        self._fetching = False

    @property
    def runner(self) -> CommandRunner:
        if self._runner is None:
            self._runner = CommandRunner()
            self._runner.line.connect(self.log.append)
            self._runner.finished.connect(self._finished)
        return self._runner

    @property
    def running(self) -> bool:
        return self._runner is not None and self._runner.running

    # connection state

    def refresh_state(self, ctx: PluginContext) -> None:
        if self._fetching or self.running:
            return
        self._fetching = True
        run_in_thread(network.current_state, lambda result, error: self._state_ready(ctx, result, error))

    def _state_ready(self, ctx: PluginContext, result: str | None, error: Exception | None) -> None:
        self._fetching = False
        self._state_at = time.monotonic()
        before = (self.state, self.state_error)
        if error is not None:
            self.state, self.state_error = None, str(error)
        else:
            self.state, self.state_error = result, None
        if (self.state, self.state_error) != before:
            ctx.notify_changed()

    # tile

    def tile_active(self, ctx: PluginContext) -> bool | None:
        if not self.running and time.monotonic() - self._state_at > STATE_STALE_S:
            self.refresh_state(ctx)
        return self.running

    def tile_subtitle(self, ctx: PluginContext) -> str:
        if self.running:
            return "Wird neu gestartet …"
        if self.last_result:
            return self.last_result
        if self.state_error:
            return "NetworkManager nicht erreichbar"
        if self.state is None:
            return "Prüfe …"
        return network.describe_state(self.state)

    def toggle(self, ctx: PluginContext) -> None:
        self.restart(ctx)

    # restart

    def restart(self, ctx: PluginContext) -> None:
        if self.running:
            return
        self._ctx = ctx
        self.last_result = None
        self.log.clear()
        runner = self.runner
        runner.started.emit()
        runner.line.emit(f"$ {COMMAND}")
        runner.start(COMMAND)
        ctx.notify_changed()

    def _finished(self, code: int) -> None:
        ctx = self._ctx
        if code == 0:
            self.last_result, message = None, "Fertig."
        elif code in POLKIT_DISMISSED:
            self.last_result, message = "Abgebrochen", "Abgebrochen (keine Berechtigung)."
        else:
            self.last_result, message = f"Fehlgeschlagen (Code {code})", f"Fehlgeschlagen (Code {code})."
        self.runner.line.emit(message)
        self._state_at = 0.0
        if ctx is not None:
            ctx.notify_changed()
            self.refresh_state(ctx)
            QTimer.singleShot(RECHECK_DELAY_MS, lambda: self.refresh_state(ctx))

    # detail page

    def create_widget(self, ctx: PluginContext) -> QWidget:
        return NetworkPage(self, ctx)


class NetworkPage(QWidget):
    def __init__(self, plugin: NetworkPlugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx

        self.status = QLabel()
        palette = self.status.palette()
        palette.setColor(self.status.foregroundRole(), theme.TEXT_DIM)
        self.status.setPalette(palette)

        self.button = Button("NetworkManager neu starten", primary=True)
        self.button.clicked.connect(lambda: plugin.restart(ctx))

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(LOG_LINES)
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # wheel scrolling only
        self.log_view.setPlaceholderText("Ausgabe erscheint hier")
        self.log_view.setPlainText("\n".join(plugin.log))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.status)
        layout.addWidget(self.button)
        layout.addWidget(self.log_view, 1)

        plugin.runner.started.connect(self.log_view.clear)
        plugin.runner.line.connect(self._append)
        ctx.changed.connect(self._update)
        self._update()

    def _append(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _update(self) -> None:
        self.status.setText(self.plugin.tile_subtitle(self.ctx))
        self.button.setEnabled(not self.plugin.running)


PLUGIN = NetworkPlugin()
