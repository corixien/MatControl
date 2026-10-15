from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .plugin_base import Plugin, PluginContext

TILE_STYLE = """
#tile { background: palette(button); border-radius: 14px; }
#tile[state="on"] { background: palette(highlight); }
#tile[state="on"] QLabel { color: palette(highlighted-text); }
#tileIcon { border: none; border-radius: 22px; background: rgba(128, 128, 128, 70); }
#tile[state="on"] #tileIcon { background: rgba(255, 255, 255, 70); }
"""


def toggle_plugin(plugin: Plugin, ctx: PluginContext) -> None:
    plugin.toggle(ctx)
    ctx.notify_changed()


class Switch(QAbstractButton):
    """Small on/off switch (Qt has none)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        track = palette.highlight() if self.isChecked() else palette.mid()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.setOpacity(1.0 if self.isEnabled() else 0.4)
        h = self.height()
        painter.drawRoundedRect(QRectF(0, 0, self.width(), h), h / 2, h / 2)
        painter.setBrush(Qt.GlobalColor.white)
        x = self.width() - h + 3 if self.isChecked() else 3
        painter.drawEllipse(QRectF(x, 3, h - 6, h - 6))


class Tile(QFrame):
    """Quick-settings tile: icon click toggles, click anywhere else opens the details."""

    opened = Signal()

    def __init__(self, plugin: Plugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx
        self.setObjectName("tile")
        self.setStyleSheet(TILE_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(70)

        self.icon_button = QToolButton()
        self.icon_button.setObjectName("tileIcon")
        self.icon_button.setIcon(QIcon.fromTheme(plugin.icon))
        self.icon_button.setIconSize(QSize(24, 24))
        self.icon_button.setFixedSize(44, 44)
        self.icon_button.clicked.connect(self._on_icon_clicked)

        self.title = QLabel(plugin.name)
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.subtitle = QLabel()
        sub_font = self.subtitle.font()
        sub_font.setPointSizeF(max(sub_font.pointSizeF() - 1, 7))
        self.subtitle.setFont(sub_font)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addStretch(1)
        texts.addWidget(self.title)
        texts.addWidget(self.subtitle)
        texts.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self.icon_button)
        layout.addLayout(texts, 1)

        ctx.changed.connect(self.refresh)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self) -> None:
        active = self.plugin.tile_active(self.ctx)
        state = "none" if active is None else ("on" if active else "off")
        if self.property("state") != state:
            self.setProperty("state", state)
            self.style().unpolish(self)
            self.style().polish(self)
        self.subtitle.setText(self.plugin.tile_subtitle(self.ctx))

    def _on_icon_clicked(self) -> None:
        if self.plugin.toggleable:
            toggle_plugin(self.plugin, self.ctx)
        else:
            self.opened.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.opened.emit()
        super().mousePressEvent(event)


class DetailPage(QWidget):
    """Header (back, title, optional on/off switch) above the plugin's own widget."""

    back = Signal()

    def __init__(self, plugin: Plugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx

        back_button = QToolButton()
        back_button.setIcon(QIcon.fromTheme("go-previous"))
        back_button.setAutoRaise(True)
        back_button.clicked.connect(self.back)

        title = QLabel(plugin.name)
        font = title.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() + 2)
        title.setFont(font)

        header = QHBoxLayout()
        header.addWidget(back_button)
        header.addWidget(title, 1)

        self.switch: Switch | None = None
        if plugin.toggleable:
            self.switch = Switch()
            self.switch.clicked.connect(lambda: toggle_plugin(plugin, ctx))
            header.addWidget(self.switch)
            ctx.changed.connect(self._sync_switch)
            self._sync_switch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(header)
        layout.addWidget(plugin.create_widget(ctx), 1)

    def _sync_switch(self) -> None:
        if self.switch is not None:
            self.switch.setChecked(bool(self.plugin.tile_active(self.ctx)))
