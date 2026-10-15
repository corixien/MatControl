import time

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer
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
from .widgets import DetailPage, PageStack, Tile

COLUMNS = 2
SHOW_MS = 340
HIDE_MS = 260
GRACE_S = 0.6  # ignore focus loss right after opening (compositor may bounce activation)


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
        for plugin in plugins:
            ctx = self._contexts[plugin.id]
            page = DetailPage(plugin, ctx)
            page.back.connect(self.show_home)
            self.stack.addWidget(page)
            self.pages[plugin.id] = page
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(1, 0, 1, 1)
        panel_layout.addWidget(self.stack)

        self._anim = QPropertyAnimation(self.panel, b"pos", self)
        self._anim.finished.connect(self._animation_finished)

    def _build_home(self, config: Config, plugins: list[Plugin], errors: list[str]) -> QWidget:
        self._contexts = {p.id: PluginContext(config, p.id) for p in plugins}
        self.tiles: list[Tile] = []
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(10)
        for column in range(COLUMNS):
            grid.setColumnStretch(column, 1)
        for index, plugin in enumerate(plugins):
            tile = Tile(plugin, self._contexts[plugin.id])
            tile.opened.connect(lambda pid=plugin.id: self.open_plugin(pid))
            self.tiles.append(tile)
            grid.addWidget(tile, index // COLUMNS, index % COLUMNS)
        rows = (len(plugins) + COLUMNS - 1) // COLUMNS
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
        scroll.setWidget(content)
        content.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    # navigation

    def show_home(self) -> None:
        self.stack.setCurrentIndex(0)

    def open_plugin(self, plugin_id: str) -> None:
        self.stack.setCurrentWidget(self.pages[plugin_id])

    # slide animation

    def show_animated(self) -> None:
        self._anim.stop()
        self._hiding = False
        self._show_token += 1
        self.show_home()
        self._opened_at = time.monotonic()
        if not self.popup:
            self.show()
            self.raise_()
            self.activateWindow()
            return
        self.panel.move(0, -self.height())  # fully above, invisible until the slide starts
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
            QTimer.singleShot(40, lambda: self._begin_show_slide(token))
        else:
            QTimer.singleShot(8, lambda: self._start_when_exposed(token, tries + 1))

    def _begin_show_slide(self, token: int) -> None:
        if token != self._show_token or self._hiding or not self.isVisible():
            return
        self._slide(QPoint(0, 0), SHOW_MS, QEasingCurve.Type.OutCubic)
        for index, tile in enumerate(self.tiles):
            tile.play_intro(90 + 45 * index)

    def hide_animated(self) -> None:
        if not self.isVisible() or self._hiding:
            return
        if not self.popup:
            self.hide()
            return
        self._show_token += 1  # cancels a pending show
        self._hiding = True
        self._slide(QPoint(0, -self.height()), HIDE_MS, QEasingCurve.Type.InCubic)

    def toggle(self) -> None:
        """Tray click: open when closed, close when open."""
        if self.isVisible() and not self._hiding:
            self.hide_animated()
        elif not self.isVisible() and time.monotonic() - self.last_hidden > 0.25:
            self.show_animated()

    def _slide(self, end: QPoint, duration: int, curve: QEasingCurve.Type) -> None:
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(curve)
        self._anim.setStartValue(self.panel.pos())
        self._anim.setEndValue(end)
        self._anim.start()

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
