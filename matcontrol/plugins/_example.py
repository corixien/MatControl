"""Template plugin. Files starting with "_" are ignored by the loader.

Copy this file to matcontrol/plugins/<name>.py and edit. See HOWTOADDAFUNCTION.md.
To preview it in the app: MATCONTROL_LOAD_EXAMPLE=1 python -m matcontrol
"""

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..plugin_base import Plugin, PluginContext


class ExamplePlugin(Plugin):
    id = "example"
    name = "Beispiel"
    icon = "applications-system"
    order = 900

    # Home tile: on/off color and status line.
    def tile_active(self, ctx: PluginContext) -> bool | None:
        return bool(ctx.settings.get("enabled", False))

    def tile_subtitle(self, ctx: PluginContext) -> str:
        return "An" if self.tile_active(ctx) else "Aus"

    # Tile icon click and the detail-page switch call this. Omit it for a plugin without on/off.
    def toggle(self, ctx: PluginContext) -> None:
        ctx.settings["enabled"] = not ctx.settings.get("enabled", False)
        ctx.save()

    # Detail page: all settings and controls of this plugin.
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
