"""Update: run one configurable "update everything" command as root, with a live log.

Tile: the icon disc is tinted when updates are pending, inverts (white) while the update
runs. Clicking the icon (or the switch on the detail page) starts the update. The command
runs through pkexec (Polkit password dialog), never sudo.
"""

import time
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from .. import theme, updates
from ..plugin_base import Plugin, PluginContext
from ..runner import POLKIT_DISMISSED, CommandRunner
from ..tasks import run_in_thread
from ..widgets import Button

# dnf + system flatpaks + firmware, all non-interactive (-y). fwupdmgr exits 2 when there is nothing to do.
DEFAULT_COMMAND = (
    "dnf upgrade -y && flatpak update -y && "
    '{ fwupdmgr update -y --no-reboot-check; rc=$?; [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ]; }'
)
CHECK_INTERVAL_S = 3600
LOG_LINES = 2000


class UpdatePlugin(Plugin):
    id = "update"
    name = "Update"
    icon = "system-software-update"
    order = 20

    def __init__(self) -> None:
        self.status: updates.UpdateStatus | None = None
        self.last_result: str | None = None  # shown until the next check, e.g. "Fehlgeschlagen (Code 1)"
        self.log: deque[str] = deque(maxlen=LOG_LINES)
        self._runner: CommandRunner | None = None
        self._ctx: PluginContext | None = None  # context of the running update
        self._checked_at = 0.0
        self._checking = False

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

    def command(self, ctx: PluginContext) -> str:
        return (ctx.settings.get("command") or DEFAULT_COMMAND).strip()

    # update detection

    def check(self, ctx: PluginContext) -> None:
        if self._checking or self.running:
            return
        self._checking = True
        ctx.notify_changed()
        run_in_thread(updates.check, lambda result, error: self._checked(ctx, result, error))

    def _checked(self, ctx: PluginContext, result: updates.UpdateStatus | None, error: Exception | None) -> None:
        self._checking = False
        self._checked_at = time.monotonic()
        self.status = result if error is None else updates.UpdateStatus(error=str(error))
        if self.status.error is None and self.last_result and self.last_result.startswith("Fertig"):
            self.last_result = None
        ctx.notify_changed()

    # tile

    def tile_active(self, ctx: PluginContext) -> bool | None:
        if not self.running and not self._checking and time.monotonic() - self._checked_at > CHECK_INTERVAL_S:
            self.check(ctx)
        return self.running

    def tile_attention(self, ctx: PluginContext) -> bool:
        return not self.running and bool(self.status and self.status.count > 0)

    def tile_subtitle(self, ctx: PluginContext) -> str:
        if self.running:
            return "Wird aktualisiert …"
        if self.last_result and not self.last_result.startswith("Fertig"):
            return self.last_result
        if self._checking:
            return "Suche Updates …"
        if self.status is None:
            return "Prüfe …"
        if self.status.error:
            return "Prüfung fehlgeschlagen"
        if self.status.count:
            return f"{self.status.count} Updates verfügbar"
        return "System aktuell"

    def toggle(self, ctx: PluginContext) -> None:
        self.start(ctx)

    # running the update

    def start(self, ctx: PluginContext) -> None:
        if self.running:
            return
        command = self.command(ctx)
        self.last_result = None
        self.log.clear()
        self._ctx = ctx
        runner = self.runner
        runner.started.emit()
        runner.line.emit(f"$ {command}")
        runner.start(command)
        ctx.notify_changed()

    def _finished(self, code: int) -> None:
        ctx = self._ctx
        if code == 0:
            self.last_result, message = "Fertig", "Fertig."
        elif code in POLKIT_DISMISSED:
            self.last_result, message = "Abgebrochen", "Abgebrochen (keine Berechtigung)."
        else:
            self.last_result, message = f"Fehlgeschlagen (Code {code})", f"Fehlgeschlagen (Code {code})."
        self.runner.line.emit(message)
        self._checked_at = 0.0
        if ctx is not None:
            ctx.notify_changed()
            self.check(ctx)

    # detail page

    def create_widget(self, ctx: PluginContext) -> QWidget:
        return UpdatePage(self, ctx)


class UpdatePage(QWidget):
    def __init__(self, plugin: UpdatePlugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx

        self.status = QLabel()
        palette = self.status.palette()
        palette.setColor(self.status.foregroundRole(), theme.TEXT_DIM)
        self.status.setPalette(palette)

        self.command = QLineEdit(plugin.command(ctx))
        self.command.setPlaceholderText(DEFAULT_COMMAND)
        self.command.setClearButtonEnabled(False)
        self.command.editingFinished.connect(self._save_command)
        command_label = QLabel("Befehl (läuft als root über pkexec)")
        command_label.setPalette(palette)

        self.check_button = Button("Jetzt prüfen")
        self.check_button.clicked.connect(lambda: plugin.check(ctx))
        self.start_button = Button("Update starten", primary=True)
        self.start_button.clicked.connect(self._start)
        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.start_button)

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
        layout.addWidget(command_label)
        layout.addWidget(self.command)
        layout.addLayout(buttons)
        layout.addWidget(self.log_view, 1)

        plugin.runner.started.connect(self.log_view.clear)
        plugin.runner.line.connect(self._append)
        ctx.changed.connect(self._update)
        self._update()

    def _append(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _save_command(self) -> None:
        text = self.command.text().strip()
        if text and text != DEFAULT_COMMAND:
            self.ctx.settings["command"] = text
        else:
            self.ctx.settings.pop("command", None)
        self.ctx.save()

    def _start(self) -> None:
        self._save_command()
        self.plugin.start(self.ctx)

    def _update(self) -> None:
        running = self.plugin.running
        self.status.setText(self.plugin.tile_subtitle(self.ctx))
        self.start_button.setEnabled(not running)
        self.check_button.setEnabled(not running and not self.plugin._checking)
        self.command.setEnabled(not running)


PLUGIN = UpdatePlugin()
