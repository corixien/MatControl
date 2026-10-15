from PySide6.QtWidgets import QWidget

from .config import Config


class PluginContext:
    """What a plugin gets from the app: its own persistent settings."""

    def __init__(self, config: Config, plugin_id: str):
        self._config = config
        self.plugin_id = plugin_id

    @property
    def settings(self) -> dict:
        return self._config.plugin(self.plugin_id)

    def save(self) -> None:
        self._config.save()


class Plugin:
    """Base class. One subclass per file in matcontrol/plugins/."""

    id: str = ""  # unique, lowercase, used as config key
    name: str = ""  # German label in the sidebar
    icon: str = "applications-system"  # freedesktop theme icon name
    order: int = 100  # sidebar position, lower first

    def create_widget(self, ctx: PluginContext) -> QWidget:
        raise NotImplementedError
