import time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QHideEvent, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from .config import Config
from .plugin_base import Plugin, PluginContext


class MainWindow(QMainWindow):
    def __init__(self, config: Config, plugins: list[Plugin], errors: list[str], popup: bool = True):
        super().__init__()
        self.setWindowTitle("MatControl")
        self.popup = popup
        self.hide_on_close = False  # set by the app when a tray icon exists
        self.last_hidden = 0.0  # time.monotonic() of the last hide, for tray click races
        if popup:
            # Frameless panel-style popup; the KWin script in kwin/ places it under the panel.
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self.resize(520, 460)
        else:
            self.resize(820, 520)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(150)
        self.stack = QStackedWidget()

        for plugin in plugins:
            item = QListWidgetItem(QIcon.fromTheme(plugin.icon), plugin.name)
            self.sidebar.addItem(item)
            self.stack.addWidget(plugin.create_widget(PluginContext(config, plugin.id)))

        if errors:
            self.sidebar.addItem(QListWidgetItem(QIcon.fromTheme("dialog-warning"), "Fehler"))
            label = QLabel("Plugins konnten nicht geladen werden:\n\n" + "\n".join(errors))
            label.setWordWrap(True)
            self.stack.addWidget(label)
        elif not plugins:
            self.sidebar.addItem(QListWidgetItem("Keine Plugins"))
            self.stack.addWidget(QLabel("Keine Plugins gefunden."))

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        central = QWidget()
        if popup:
            central.setObjectName("root")
            central.setStyleSheet("#root { border: 1px solid palette(mid); }")
        layout = QHBoxLayout(central)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def changeEvent(self, event: QEvent) -> None:
        if (
            event.type() == QEvent.Type.ActivationChange
            and self.popup
            and self.isVisible()
            and not self.isActiveWindow()
        ):
            self.hide()
        super().changeEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        self.last_hidden = time.monotonic()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_on_close:
            event.ignore()
            self.hide()
        else:
            event.accept()
