"""Template plugin. Files starting with "_" are ignored by the loader.

Copy this file to matcontrol/plugins/<name>.py and edit. See HOWTOADDAFUNCTION.md.
"""

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..plugin_base import Plugin, PluginContext


class ExamplePlugin(Plugin):
    id = "example"
    name = "Beispiel"
    icon = "applications-system"
    order = 900

    def create_widget(self, ctx: PluginContext) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel()
        button = QPushButton("Zählen")

        def refresh() -> None:
            label.setText(f"Klicks: {ctx.settings.get('clicks', 0)}")

        def on_click() -> None:
            ctx.settings["clicks"] = ctx.settings.get("clicks", 0) + 1
            ctx.save()
            refresh()

        button.clicked.connect(on_click)
        layout.addWidget(label)
        layout.addWidget(button)
        layout.addStretch(1)
        refresh()
        return widget


PLUGIN = ExamplePlugin()
