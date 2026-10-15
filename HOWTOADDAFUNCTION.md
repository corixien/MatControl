# How to add a function

Every function of MatControl is one plugin: one Python file in `matcontrol/plugins/`. The app finds it automatically. No other file needs to change.

## Steps

1. Copy `matcontrol/plugins/_example.py` to `matcontrol/plugins/<name>.py` (lowercase, no leading underscore; files starting with `_` are ignored).
2. Rename the class. Set `id` (unique, lowercase, used as config key), `name` (German tile label), `icon` (freedesktop theme icon name, e.g. `network-wired`, `audio-card`, `system-software-update`), and `order` (tile position, lower first).
3. Build the detail page in `create_widget(self, ctx)` and return a `QWidget`. Shown when the user clicks beside the tile icon; put all settings and controls here.
3a. Tile (home page, quick-settings style): override `tile_active(ctx)` (`True`/`False` colors the tile on/off, `None` = neutral tile without state) and `tile_subtitle(ctx)` (short German status, e.g. "Update verfügbar", "Aktiv"). Both run on the UI thread every 5 s, so keep them cheap: read cached state or settings, never run slow commands there.
3b. On/off: override `toggle(ctx)` to make the tile icon click and the switch in the detail header work. Omit it for plugins without on/off; then the icon click opens the detail page. After changing state outside `toggle`, call `ctx.notify_changed()` so tile and switch refresh immediately.
4. Keep `PLUGIN = YourPlugin()` at module level. The loader reads exactly this name.
5. Add a test in `tests/` for any logic that does not need a display (command building, parsing).
6. Run `.venv/bin/python -m pytest`, then start the app and check the new tile. Preview the template with `MATCONTROL_LOAD_EXAMPLE=1 .venv/bin/python -m matcontrol`.

## Rules

- UI text is German.
- Persistent settings: `ctx.settings` (a dict), then `ctx.save()`. Never write config files yourself.
- Long-running or external commands: use `QProcess`, never block the UI thread with `subprocess.run`.
- Commands that need root: run them through `pkexec` (Polkit dialog). Never hard-code `sudo`, never store passwords.
- A plugin that raises on import is shown in the "Fehler" page and does not crash the app.
- No secrets in the repo (it is public).
- Do not change core files (`app.py`, `window.py`, `plugin_loader.py`) just to add a function. If the plugin API is missing something, extend `plugin_base.py` and update this file.

## Minimal skeleton

```python
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..plugin_base import Plugin, PluginContext


class HelloPlugin(Plugin):
    id = "hello"
    name = "Hallo"
    icon = "dialog-information"

    def tile_active(self, ctx):
        return None  # or True/False

    def tile_subtitle(self, ctx):
        return "Bereit"

    def create_widget(self, ctx: PluginContext) -> QWidget:
        widget = QWidget()
        QVBoxLayout(widget).addWidget(QLabel("Hallo"))
        return widget


PLUGIN = HelloPlugin()
```
