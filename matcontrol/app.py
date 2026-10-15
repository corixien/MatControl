import logging
import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import Config
from .plugin_loader import discover
from .window import MainWindow


def build_tray(app: QApplication, window: MainWindow) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = QSystemTrayIcon(QIcon.fromTheme("preferences-system"), app)
    tray.setToolTip("MatControl")

    menu = QMenu()
    open_action = QAction("Öffnen", menu)
    open_action.triggered.connect(lambda: (window.show(), window.raise_(), window.activateWindow()))
    quit_action = QAction("Beenden", menu)
    quit_action.triggered.connect(lambda: (setattr(window, "hide_on_close", False), app.quit()))
    menu.addAction(open_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)

    def on_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if window.isVisible():
                window.hide()
            else:
                open_action.trigger()

    tray.activated.connect(on_activated)
    tray.show()
    return tray


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("MatControl")
    app.setQuitOnLastWindowClosed(False)

    plugins, errors = discover()
    window = MainWindow(Config(), plugins, errors)
    tray = build_tray(app, window)
    window.hide_on_close = tray is not None

    if "--minimized" not in sys.argv[1:] or tray is None:
        window.show()
    return app.exec()
