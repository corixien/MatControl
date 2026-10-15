"""Single place for colors and the dark stylesheet. Flat tones only, no gradients."""

from PySide6.QtGui import QColor, QPalette

BG = QColor("#0f0f0f")
SURFACE = QColor("#1a1a1a")
SURFACE_HOVER = QColor("#232323")
SURFACE_PRESS = QColor("#2b2b2b")
BORDER = QColor("#242424")
ON = QColor("#e8e8e8")  # active tiles/switches: inverted, monochrome
ON_HOVER = QColor("#ffffff")
TEXT = QColor("#e6e6e6")
TEXT_DIM = QColor("#8a8a8a")
TEXT_ON = QColor("#0f0f0f")  # text on an ON surface
TEXT_ON_DIM = QColor("#5c5c5c")
TRACK_OFF = QColor("#2a2a2a")
KNOB_OFF = QColor("#9a9a9a")


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
    edge = (
        "border-top: none; border-bottom-left-radius: 14px; border-bottom-right-radius: 14px;"
        if popup
        else ""
    )
    return f"""
#panel {{ background: {BG.name()}; border: 1px solid {BORDER.name()}; {edge} }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2e2e2e; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: #444444; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {SURFACE.name()}; border: 1px solid {BORDER.name()}; border-radius: 10px;
    padding: 6px 10px; selection-background-color: {ON.name()}; selection-color: {TEXT_ON.name()};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: #3c3c3c; }}
QPushButton {{ background: {SURFACE.name()}; border: none; border-radius: 10px; padding: 8px 16px; }}
QPushButton:hover {{ background: {SURFACE_HOVER.name()}; }}
QPushButton:pressed {{ background: {SURFACE_PRESS.name()}; }}
QToolTip {{ background: {SURFACE_PRESS.name()}; color: {TEXT.name()}; border: 1px solid {BORDER.name()}; }}
"""
