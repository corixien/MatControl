from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from .config import Config


class PluginContext(QObject):
    """What a plugin gets from the app: persistent settings and a change signal.

    Emit `changed` (via notify_changed) whenever the plugin state changed so the
    home tile and the detail switch refresh.
    """

    changed = Signal()

    def __init__(self, config: Config, plugin_id: str):
        super().__init__()
        self._config = config
        self.plugin_id = plugin_id

    @property
    def settings(self) -> dict:
        return self._config.plugin(self.plugin_id)

    def save(self) -> None:
        self._config.save()

    def notify_changed(self) -> None:
        self.changed.emit()


class Plugin:
    """Base class. One subclass per file in matcontrol/plugins/."""

    id: str = ""  # unique, lowercase, used as config key
    name: str = ""  # German label on the home tile and detail header
    icon: str = "applications-system"  # freedesktop theme icon name
    order: int = 100  # tile position, lower first

    def create_widget(self, ctx: PluginContext) -> QWidget:
        """Detail page shown when the user clicks beside the tile icon."""
        raise NotImplementedError

    # Home tile. These run on the UI thread every few seconds: keep them cheap.

    def tile_active(self, ctx: PluginContext) -> bool | None:
        """True/False colors the tile on/off. None = no on/off state (neutral tile)."""
        return None

    def tile_attention(self, ctx: PluginContext) -> bool:
        """True tints the idle tile icon with the accent color (something needs the user, e.g. an update).
        Ignored while tile_active() is True."""
        return False

    def tile_subtitle(self, ctx: PluginContext) -> str:
        """Short status line under the name, e.g. "Update verfügbar" or "Aktiv"."""
        return ""

    def toggle(self, ctx: PluginContext) -> None:
        """Override to make the tile icon (and the detail switch) toggle the plugin."""

    @property
    def toggleable(self) -> bool:
        return type(self).toggle is not Plugin.toggle
