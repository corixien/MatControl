import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import Config
from .plugin_loader import discover
from .window import MainWindow

ICON_PATH = Path(__file__).parent / "data" / "matcontrol.svg"
SOCKET_NAME = "matcontrol"
TRAY_RETRIES = 60  # autostart can run before the panel (and its tray) exists


def app_icon() -> QIcon:
    return QIcon.fromTheme("matcontrol", QIcon(str(ICON_PATH)))


def socket_name() -> str:
    return os.environ.get("MATCONTROL_SOCKET", SOCKET_NAME)


def notify_running_instance(name: str) -> bool:
    """If MatControl already runs, ask it to open its popup and report True."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def serve(app: QApplication, window: MainWindow, name: str) -> QLocalServer:
    """Listen for later launches (app menu, shortcut) and open the popup for them."""
    QLocalServer.removeServer(name)  # stale socket of a crashed instance
    server = QLocalServer(app)
    server.listen(name)

    def on_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is not None:
            connection.disconnectFromServer()
            connection.deleteLater()
        window.show_animated()

    server.newConnection.connect(on_connection)
    return server


def build_tray(app: QApplication, window: MainWindow) -> QSystemTrayIcon | None:
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip("MatControl")

    menu = QMenu()
    open_action = QAction("Öffnen", menu)
    open_action.triggered.connect(window.show_animated)
    quit_action = QAction("Beenden", menu)
    quit_action.triggered.connect(lambda: (setattr(window, "hide_on_close", False), app.quit()))
    menu.addAction(open_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)

    def on_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            window.toggle()

    tray.activated.connect(on_activated)
    tray.show()
    return tray


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("MatControl")
    app.setDesktopFileName("matcontrol")  # Wayland app_id, matched by the KWin script
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    if notify_running_instance(socket_name()):
        return 0  # the running instance opens its popup

    args = sys.argv[1:]
    plugins, errors = discover()
    window = MainWindow(Config(), plugins, errors, popup="--window" not in args)
    server = serve(app, window, socket_name())  # noqa: F841  (kept alive until exit)
    minimized = "--minimized" in args
    holder: dict[str, QSystemTrayIcon | None] = {"tray": build_tray(app, window)}
    window.hide_on_close = holder["tray"] is not None

    if holder["tray"] is None and minimized:
        # started at login: wait for the panel's tray instead of opening a window
        retries = {"left": TRAY_RETRIES}
        timer = QTimer(app)
        timer.setInterval(1000)

        def retry() -> None:
            retries["left"] -= 1
            holder["tray"] = build_tray(app, window)
            if holder["tray"] is not None:
                window.hide_on_close = True
                timer.stop()
            elif retries["left"] <= 0:
                timer.stop()
                window.show_animated()  # no tray at all: still make the app reachable

        timer.timeout.connect(retry)
        timer.start()
    elif not minimized or holder["tray"] is None:
        window.show_animated()
    return app.exec()
