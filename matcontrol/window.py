from PySide6.QtGui import QCloseEvent, QIcon
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
    def __init__(self, config: Config, plugins: list[Plugin], errors: list[str]):
        super().__init__()
        self.setWindowTitle("MatControl")
        self.resize(820, 520)
        self.hide_on_close = False  # set by the app when a tray icon exists

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
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
        layout = QHBoxLayout(central)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.hide_on_close:
            event.ignore()
            self.hide()
        else:
            event.accept()
