import time

from PySide6.QtCore import QEasingCurve, QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QHideEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .config import Config
from .plugin_base import Plugin, PluginContext
from .widgets import Card, DetailPage, PageStack, Tile

COLUMNS = 4  # grid cells; a normal tile spans 2 columns x 1 row
SHOW_MS = 340
HIDE_MS = 260
OVERSHOOT = 24  # extra distance so no sub-pixel edge of the panel stays visible when closed
SETTLE_MS = 100  # after the window is exposed, give KWin time to place it
MAX_STEP_S = 1 / 30  # a stall (window mapping, placement) delays the slide instead of skipping it
GRACE_S = 0.6  # ignore focus loss right after opening (compositor may bounce activation)


def place_tiles(plugins: list[Plugin]) -> dict[str, tuple[int, int]]:
    """Grid cell (row, column) per plugin id. Pinned tiles take their corner first, the others
    fill the remaining cells left to right, top to bottom."""
    taken: set[tuple[int, int]] = set()
    placed: dict[str, tuple[int, int]] = {}

    def fits(row: int, column: int, width: int, height: int) -> bool:
        cells = {(r, c) for r in range(row, row + height) for c in range(column, column + width)}
        return column + width <= COLUMNS and not cells & taken

    def take(plugin: Plugin, row: int, column: int) -> None:
        width, height = plugin.tile_cells
        taken.update((r, c) for r in range(row, row + height) for c in range(column, column + width))
        placed[plugin.id] = (row, column)

    for plugin in plugins:
        if plugin.tile_pin == "top-right":
            take(plugin, 0, COLUMNS - plugin.tile_cells[0])
    for plugin in plugins:
        if plugin.id in placed:
            continue
        width, height = plugin.tile_cells
        row = 0
        while plugin.id not in placed:
            for column in range(0, COLUMNS - width + 1, 2):  # tiles sit on the 2-column raster
                if fits(row, column, width, height):
                    take(plugin, row, column)
                    break
            row += 1
    return placed


class _Slide(QObject):
    """Vertical slide of the panel that never skips ahead after a stall."""

    def __init__(self, panel: QWidget, on_finished) -> None:
        super().__init__(panel)
        self._panel = panel
        self._on_finished = on_finished
        self._timer = QTimer(self)
        self._timer.setInterval(8)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._start_y = self._end_y = 0
        self._duration = 1.0
        self._elapsed = 0.0
        self._last = 0.0
        self._curve = QEasingCurve()

    def start(self, end_y: int, duration_ms: int, curve: QEasingCurve.Type) -> None:
        self._start_y = self._panel.y()
        self._end_y = end_y
        self._duration = duration_ms / 1000
        self._curve = QEasingCurve(curve)
        self._elapsed = 0.0
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.monotonic()
        self._elapsed += min(now - self._last, MAX_STEP_S)
        self._last = now
        t = min(self._elapsed / self._duration, 1.0)
        y = self._start_y + (self._end_y - self._start_y) * self._curve.valueForProgress(t)
        self._panel.move(0, round(y))
        if t >= 1.0:
            self._timer.stop()
            self._on_finished()


class _Holder(QWidget):
    """Central widget: keeps the (animated) panel at full size."""

    def __init__(self) -> None:
        super().__init__()
        self.panel = QWidget(self)
        self.panel.setObjectName("panel")
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.panel.resize(self.size())
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, config: Config, plugins: list[Plugin], errors: list[str], popup: bool = True):
        super().__init__()
        self.setWindowTitle("MatControl")
        self.popup = popup
        self.hide_on_close = False  # set by the app when a tray icon exists
        self.last_hidden = 0.0  # time.monotonic() of the last hide, for tray click races
        self._hiding = False
        self._opened_at = 0.0
        self._show_token = 0

        holder = _Holder()
        self.panel = holder.panel
        self.setCentralWidget(holder)
        if popup:
            # Frameless slide-down popup; the KWin script in kwin/ places it under the panel.
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.resize(460, 420)
        else:
            self.resize(560, 480)
        # app-wide: a stylesheet on the panel would reset a palette set on the panel itself
        QApplication.setPalette(theme.dark_palette())
        self.panel.setStyleSheet(theme.stylesheet(popup))

        self.stack = PageStack()
        self.stack.addWidget(self._build_home(config, plugins, errors))
        self.pages: dict[str, QWidget] = {}
        self.plugins = {p.id: p for p in plugins}
        for plugin in plugins:
            if not plugin.has_detail:
                continue
            ctx = self._contexts[plugin.id]
            page = DetailPage(plugin, ctx)
            page.back.connect(self.show_home)
            self.stack.addWidget(page)
            self.pages[plugin.id] = page
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(1, 0, 1, 1)
        panel_layout.addWidget(self.stack)

        self._slide_anim = _Slide(self.panel, self._animation_finished)

    def _build_home(self, config: Config, plugins: list[Plugin], errors: list[str]) -> QWidget:
        self._contexts = {p.id: PluginContext(config, p.id) for p in plugins}
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(10)
        for column in range(COLUMNS):
            grid.setColumnStretch(column, 1)
        self.tiles: dict[str, QWidget] = {}
        placements = place_tiles(plugins)
        for plugin in plugins:
            ctx = self._contexts[plugin.id]
            row, column = placements[plugin.id]
            width, height = plugin.tile_cells
            body = plugin.create_tile(ctx)
            if body is None:
                tile: Card = Tile(plugin, ctx)
            else:
                tile = Card()
                layout = QVBoxLayout(tile)
                layout.setContentsMargins(14, 12, 14, 12)
                layout.addWidget(body)
            tile.opened.connect(lambda pid=plugin.id: self.open_plugin(pid))
            grid.addWidget(tile, row, column, height, width)
            self.tiles[plugin.id] = tile
            ctx.close_requested.connect(self.hide_animated)
        rows = max((placements[p.id][0] + p.tile_cells[1] for p in plugins), default=0)
        if not plugins:
            grid.addWidget(QLabel("Keine Plugins gefunden."), 0, 0)
        if errors:
            label = QLabel("Plugins konnten nicht geladen werden:\n" + "\n".join(errors))
            label.setWordWrap(True)
            grid.addWidget(label, rows + 1, 0, 1, COLUMNS)
        grid.setRowStretch(rows + 2, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # wheel scrolling only
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        content.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    # navigation

    def show_home(self) -> None:
        self.stack.setCurrentIndex(0)

    def open_plugin(self, plugin_id: str) -> None:
        plugin = self.plugins[plugin_id]
        if plugin.has_detail:
            self.stack.setCurrentWidget(self.pages[plugin_id])
        else:
            plugin.tile_clicked(self._contexts[plugin_id])

    # slide animation

    def show_animated(self) -> None:
        self._slide_anim.stop()
        self._hiding = False
        self._show_token += 1
        self.show_home()
        self._opened_at = time.monotonic()
        if not self.popup:
            self.show()
            self.raise_()
            self.activateWindow()
            return
        self.panel.move(0, self._hidden_y())  # fully above, invisible until the slide starts
        self.show()
        self.raise_()
        self.activateWindow()
        self._start_when_exposed(self._show_token, 0)

    def _start_when_exposed(self, token: int, tries: int) -> None:
        """Wait for the compositor to map the window, else the first part of the slide is lost."""
        if token != self._show_token:
            return
        handle = self.windowHandle()
        if (handle is not None and handle.isExposed()) or tries >= 50:
            QTimer.singleShot(SETTLE_MS, lambda: self._begin_show_slide(token))
        else:
            QTimer.singleShot(8, lambda: self._start_when_exposed(token, tries + 1))

    def _begin_show_slide(self, token: int) -> None:
        if token != self._show_token or self._hiding or not self.isVisible():
            return
        self._slide(0, SHOW_MS, QEasingCurve.Type.OutCubic)

    def hide_animated(self) -> None:
        if not self.isVisible() or self._hiding:
            return
        if not self.popup:
            self.hide()
            return
        self._show_token += 1  # cancels a pending show
        self._hiding = True
        self._slide(self._hidden_y(), HIDE_MS, QEasingCurve.Type.InCubic)

    def toggle(self) -> None:
        """Tray click: open when closed, close when open."""
        if self.isVisible() and not self._hiding:
            self.hide_animated()
        elif not self.isVisible() and time.monotonic() - self.last_hidden > 0.25:
            self.show_animated()

    def _hidden_y(self) -> int:
        return -(self.height() + OVERSHOOT)

    def _slide(self, end_y: int, duration: int, curve: QEasingCurve.Type) -> None:
        self._slide_anim.stop()
        self._slide_anim.start(end_y, duration, curve)

    def _animation_finished(self) -> None:
        if self._hiding:
            self._hiding = False
            self.hide()

    # window events

    def changeEvent(self, event: QEvent) -> None:
        if (
            event.type() == QEvent.Type.ActivationChange
            and self.popup
            and self.isVisible()
            and not self.isActiveWindow()
            and time.monotonic() - self._opened_at > GRACE_S
        ):
            self.hide_animated()
        super().changeEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        self.last_hidden = time.monotonic()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_on_close:
            event.ignore()
            self.hide_animated()
        else:
            event.accept()
