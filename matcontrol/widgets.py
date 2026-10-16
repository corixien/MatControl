"""Animated building blocks. Every state change fades; nothing snaps.

Plugin authors should use Switch and Button from here instead of the stock Qt widgets
so a plugin looks and moves like the rest of the app.
"""

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSlider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .plugin_base import Plugin, PluginContext
from .theme import mix


def toggle_plugin(plugin: Plugin, ctx: PluginContext) -> None:
    plugin.toggle(ctx)
    ctx.notify_changed()


class Fader(QObject):
    """Animated float that repaints its widget on every step.

    Jumps instantly while the widget is not visible, so hidden/offscreen widgets
    and tests always see the final value.
    """

    def __init__(
        self,
        owner: QWidget,
        duration: int = 160,
        curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__(owner)
        self.value = 0.0
        self.target = 0.0
        self._owner = owner
        self._on_change = on_change
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(curve)
        self._anim.valueChanged.connect(self._step)

    def to(self, target: float, instant: bool = False) -> None:
        self.target = target
        self._anim.stop()
        if instant or not self._owner.isVisible():
            self._step(target)
            return
        self._anim.setStartValue(float(self.value))
        self._anim.setEndValue(float(target))
        self._anim.start()

    def _step(self, value) -> None:
        self.value = float(value)
        if self._on_change:
            self._on_change()
        self._owner.update()


class _Hoverable:
    """Mixin: hover and press faders for a QWidget."""

    def _init_hover(self: QWidget, hover_ms: int = 150, press_ms: int = 90) -> None:
        self.hover = Fader(self, hover_ms)
        self.press = Fader(self, press_ms)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event) -> None:
        self.hover.to(1)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover.to(0)
        self.press.to(0)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.press.to(1)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.press.to(0)
        super().mouseReleaseEvent(event)


class Switch(_Hoverable, QAbstractButton):
    """On/off switch: the knob glides, the track cross-fades, the knob stretches while pressed."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 28)
        self._init_hover()
        self.progress = Fader(self, 220)
        self.toggled.connect(lambda checked: self.progress.to(1.0 if checked else 0.0))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if not self.isEnabled():
            p.setOpacity(0.4)
        t = self.progress.value
        w, h = self.width(), self.height()
        track = mix(theme.TRACK_OFF, theme.ON, t)
        track = mix(track, theme.ON_HOVER, self.hover.value * 0.10)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        diameter = h - 8 + 4 * self.press.value
        x = 4 + (w - 4 - diameter - 4) * t
        p.setBrush(mix(theme.KNOB_OFF, theme.BG, t))
        p.drawRoundedRect(QRectF(x, (h - diameter) / 2, diameter, diameter), diameter / 2, diameter / 2)


class IconButton(_Hoverable, QAbstractButton):
    """Round icon button. `tone` 0..1 cross-fades from the off look to the on look."""

    def __init__(self, icon_name: str, icon_size: int = 22, diameter: int = 40):
        super().__init__()
        self._icon = QIcon.fromTheme(icon_name)
        self._icon_size = icon_size
        self.setFixedSize(diameter, diameter)
        self._init_hover()
        self.tone = Fader(self, 220)
        self.bg_off = QColor(255, 255, 255, 0)
        self.bg_off_hover = theme.WASH
        self.bg_on = theme.DISC_ON
        self.bg_on_hover = theme.DISC_ON_HOVER

    def set_tone(self, on: bool) -> None:
        self.tone.to(1.0 if on else 0.0)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tone, hover = self.tone.value, self.hover.value
        background = mix(mix(self.bg_off, self.bg_off_hover, hover), mix(self.bg_on, self.bg_on_hover, hover), tone)
        center = QPointF(self.width() / 2, self.height() / 2)
        scale = 1 - 0.08 * self.press.value
        p.translate(center)
        p.scale(scale, scale)
        p.translate(-center)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(background)
        p.drawEllipse(QRectF(0, 0, self.width(), self.height()))
        pixmap = self._tinted(mix(theme.TEXT, theme.TEXT_ON, tone))
        if pixmap is not None:
            s = self._icon_size
            p.drawPixmap(QPointF((self.width() - s) / 2, (self.height() - s) / 2), pixmap)

    def _tinted(self, color: QColor) -> QPixmap | None:
        dpr = self.devicePixelRatioF()
        source = self._icon.pixmap(QSize(self._icon_size, self._icon_size), dpr)
        if source.isNull():
            return None
        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)
        tinted.setDevicePixelRatio(dpr)
        q = QPainter(tinted)
        q.drawPixmap(0, 0, source)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        q.fillRect(tinted.rect(), color)
        q.end()
        return tinted


class Slider(_Hoverable, QAbstractSlider):
    """Horizontal slider (default 0..100, setRange/setSingleStep respected). The knob glides to
    programmatic changes; `user_changed` fires only for drags/clicks."""

    user_changed = Signal(int)
    _PAD = 9  # knob radius, so the knob stays inside the widget

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setFixedHeight(26)
        self._init_hover()
        self._dragging = False
        self.shown = Fader(self, 150)
        self.valueChanged.connect(lambda v: self.shown.to(float(v), instant=self._dragging))

    def _value_at(self, x: float) -> int:
        span = max(1, self.width() - 2 * self._PAD)
        fraction = max(0.0, min(1.0, (x - self._PAD) / span))
        step = max(1, self.singleStep())
        raw = self.minimum() + fraction * (self.maximum() - self.minimum())
        return max(self.minimum(), min(self.maximum(), round(raw / step) * step))

    def _apply(self, event: QMouseEvent) -> None:
        value = self._value_at(event.position().x())
        if value != self.value():
            self.setValue(value)
            self.user_changed.emit(value)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setSliderDown(True)
            self.press.to(1)
            self._apply(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._apply(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setSliderDown(False)
            self.press.to(0)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if not self.isEnabled():
            p.setOpacity(0.4)
        w, h = self.width(), self.height()
        track_h = 6
        top = (h - track_h) / 2
        span = max(1, self.maximum() - self.minimum())
        x = self._PAD + (w - 2 * self._PAD) * (self.shown.value - self.minimum()) / span
        p.setBrush(theme.TRACK_OFF)
        p.drawRoundedRect(QRectF(self._PAD, top, w - 2 * self._PAD, track_h), 3, 3)
        p.setBrush(theme.ON)
        p.drawRoundedRect(QRectF(self._PAD, top, x - self._PAD, track_h), 3, 3)
        radius = 7 + 2 * self.hover.value + 1 * self.press.value
        p.setBrush(mix(theme.ON, theme.ON_HOVER, self.hover.value))
        p.drawEllipse(QPointF(x, h / 2), radius, radius)


class Button(_Hoverable, QPushButton):
    """Flat text button with animated hover/press. primary=True uses the inverted ON look."""

    def __init__(self, text: str = "", primary: bool = False, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.primary = primary
        self._init_hover()

    def sizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 36, 38)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        if self.primary:
            color = mix(theme.ON, theme.ON_HOVER, self.hover.value)
            color = mix(color, theme.ON_PRESS, self.press.value)
            text = theme.TEXT_ON
        else:
            color = mix(theme.SURFACE, theme.SURFACE_HOVER, self.hover.value)
            color = mix(color, theme.SURFACE_PRESS, self.press.value)
            text = theme.TEXT
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        p.setPen(text)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


class Tile(QFrame):
    """Quick-settings tile: icon click toggles, click anywhere else opens the details."""

    opened = Signal()

    def __init__(self, plugin: Plugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(74)
        self.hover = Fader(self, 160)
        self.press = Fader(self, 100)
        self.on = Fader(self, 220, on_change=self._apply_text_colors)

        self.icon_button = IconButton(plugin.icon, 22, 44)
        self.icon_button.bg_off = theme.WASH
        self.icon_button.bg_off_hover = theme.WASH_HOVER
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
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)
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
        self.setProperty("state", state)
        self.on.to(1.0 if active else 0.0)
        self.icon_button.set_tone(bool(active))
        self.subtitle.setText(self.plugin.tile_subtitle(self.ctx))

    def _apply_text_colors(self) -> None:
        for label, off, on in (
            (self.title, theme.TEXT, theme.TEXT_ON),
            (self.subtitle, theme.TEXT_DIM, theme.TEXT_ON_DIM),
        ):
            palette = label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, mix(off, on, self.on.value))
            label.setPalette(palette)

    def _on_icon_clicked(self) -> None:
        if self.plugin.toggleable:
            toggle_plugin(self.plugin, self.ctx)
        else:
            self.opened.emit()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off = mix(theme.SURFACE, theme.SURFACE_HOVER, self.hover.value)
        on = mix(theme.ON, theme.ON_HOVER, self.hover.value * 0.6)
        color = mix(off, on, self.on.value)
        color = mix(color, theme.BG, self.press.value * 0.18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(self.rect()), 16, 16)

    def enterEvent(self, event) -> None:
        self.hover.to(1)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover.to(0)
        self.press.to(0)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.press.to(1)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.press.to(0)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.opened.emit()


class DetailPage(QWidget):
    """Header (back, title, optional on/off switch) above the plugin's own widget."""

    back = Signal()

    def __init__(self, plugin: Plugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx

        back_button = IconButton("go-previous", 20, 36)
        back_button.clicked.connect(self.back)

        title = QLabel(plugin.name)
        font = title.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() + 3)
        title.setFont(font)

        header = QHBoxLayout()
        header.setSpacing(8)
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
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(plugin.create_widget(ctx), 1)

    def _sync_switch(self) -> None:
        if self.switch is not None:
            self.switch.setChecked(bool(self.plugin.tile_active(self.ctx)))


class PageStack(QWidget):
    """Stacked pages with a horizontal slide between them (QStackedWidget API subset)."""

    SLIDE_MS = 300

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._current: QWidget | None = None
        self._leaving: QWidget | None = None
        self._group: QParallelAnimationGroup | None = None

    def addWidget(self, widget: QWidget) -> int:
        widget.setParent(self)
        self._pages.append(widget)
        if self._current is None:
            self._current = widget
            widget.setGeometry(self.rect())
            widget.show()
        else:
            widget.hide()
        return len(self._pages) - 1

    def count(self) -> int:
        return len(self._pages)

    def currentWidget(self) -> QWidget | None:
        return self._current

    def currentIndex(self) -> int:
        return self._pages.index(self._current) if self._current else -1

    def setCurrentIndex(self, index: int) -> None:
        self.setCurrentWidget(self._pages[index])

    def setCurrentWidget(self, widget: QWidget) -> None:
        if widget is self._current:
            return
        self._finish()
        old = self._current
        forward = old is None or self._pages.index(widget) > self._pages.index(old)
        self._current = widget
        if old is None or not self.isVisible():
            if old is not None:
                old.hide()
            widget.setGeometry(self.rect())
            widget.show()
            return

        width, height = self.width(), self.height()
        offset = width if forward else -width
        widget.setGeometry(offset, 0, width, height)
        widget.show()
        widget.raise_()
        group = QParallelAnimationGroup(self)
        for page, start, end in ((widget, offset, 0), (old, 0, -offset)):
            anim = QPropertyAnimation(page, b"pos", group)
            anim.setDuration(self.SLIDE_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(QPoint(start, 0))
            anim.setEndValue(QPoint(end, 0))
            group.addAnimation(anim)
        self._leaving = old
        self._group = group
        group.finished.connect(self._finish)
        group.start()

    def _finish(self) -> None:
        if self._group is not None:
            group, self._group = self._group, None
            group.stop()
            group.deleteLater()
        if self._leaving is not None:
            self._leaving.hide()
            self._leaving = None
        if self._current is not None:
            self._current.setGeometry(self.rect())

    def resizeEvent(self, event) -> None:
        if self._group is None and self._current is not None:
            self._current.setGeometry(self.rect())
        super().resizeEvent(event)
