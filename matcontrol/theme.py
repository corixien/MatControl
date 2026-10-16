"""Single place for colors and the stylesheet. Flat tones derived from one base color, no gradients."""

from PySide6.QtGui import QColor, QPalette

BASE = QColor("#1a242f")  # the one theme color; everything below derives from its hue
_H, _S, _L, _ = BASE.getHslF()


def _shade(dl: float, ds: float = 1.0) -> QColor:
    """Same hue as BASE, lightness shifted by dl, saturation scaled by ds."""
    return QColor.fromHslF(_H, min(1.0, _S * ds), min(1.0, max(0.0, _L + dl)))


def _tint(lightness: float, saturation: float) -> QColor:
    """Same hue as BASE at an absolute lightness/saturation (for light surfaces and text)."""
    return QColor.fromHslF(_H, saturation, lightness)


BG = QColor(BASE)
SURFACE = _shade(0.045)
SURFACE_HOVER = _shade(0.080)
SURFACE_PRESS = _shade(0.115)
BORDER = _shade(0.140, 0.9)
FOCUS_BORDER = _shade(0.220, 0.9)
SCROLL = _shade(0.120)
SCROLL_HOVER = _shade(0.200)
TRACK_OFF = _shade(0.100)
KNOB_OFF = _shade(0.400, 0.5)
ON = _tint(0.90, 0.45)  # active tiles/switches: light surface of the theme hue
ON_HOVER = _tint(0.96, 0.50)
ON_PRESS = _tint(0.80, 0.40)
DISC_ON = _tint(0.80, 0.35)  # icon disc on an active tile
DISC_ON_HOVER = _tint(0.72, 0.35)
TEXT = _tint(0.92, 0.30)
TEXT_DIM = _tint(0.58, 0.20)
TEXT_ON = QColor(BASE)  # text on an ON surface
TEXT_ON_DIM = _tint(0.38, 0.25)
WASH = QColor(255, 255, 255, 16)  # translucent lift for idle icon discs
WASH_HOVER = QColor(255, 255, 255, 34)


def mix(a: QColor, b: QColor, t: float) -> QColor:
    """Linear RGBA blend, t clamped to 0..1."""
    t = max(0.0, min(1.0, t))
    ra, rb = a.getRgbF(), b.getRgbF()
    return QColor.fromRgbF(*(x + (y - x) * t for x, y in zip(ra, rb)))


def dark_palette() -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: SURFACE_HOVER,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: ON,
        QPalette.ColorRole.HighlightedText: TEXT_ON,
        QPalette.ColorRole.PlaceholderText: TEXT_DIM,
        QPalette.ColorRole.ToolTipBase: SURFACE_PRESS,
        QPalette.ColorRole.ToolTipText: TEXT,
    }
    for role, color in roles.items():
        palette.setColor(role, color)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, TEXT_DIM)
    return palette


def stylesheet(popup: bool) -> str:
    edge = "border-radius: 14px;" if popup else ""
    return f"""
#panel {{ background: {BG.name()}; border: 1px solid {BORDER.name()}; {edge} }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SCROLL.name()}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {SCROLL_HOVER.name()}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {SURFACE.name()}; border: 1px solid {BORDER.name()}; border-radius: 10px;
    padding: 6px 10px; selection-background-color: {ON.name()}; selection-color: {TEXT_ON.name()};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {FOCUS_BORDER.name()}; }}
QPushButton {{ background: {SURFACE.name()}; border: none; border-radius: 10px; padding: 8px 16px; }}
QPushButton:hover {{ background: {SURFACE_HOVER.name()}; }}
QPushButton:pressed {{ background: {SURFACE_PRESS.name()}; }}
QToolTip {{ background: {SURFACE_PRESS.name()}; color: {TEXT.name()}; border: 1px solid {BORDER.name()}; }}
"""
