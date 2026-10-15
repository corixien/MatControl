# How to add a function

Every function of MatControl is one plugin: one Python file in `matcontrol/plugins/`. The app finds it automatically. No other file needs to change.

## Steps

1. Copy `matcontrol/plugins/_example.py` to `matcontrol/plugins/<name>.py` (lowercase, no leading underscore; files starting with `_` are ignored).
2. Rename the class. Set `id` (unique, lowercase, used as config key), `name` (German sidebar label), `icon` (freedesktop theme icon name, e.g. `network-wired`, `audio-card`, `system-software-update`), and `order` (sidebar position, lower first).
3. Build the UI in `create_widget(self, ctx)` and return a `QWidget`.
4. Keep `PLUGIN = YourPlugin()` at module level. The loader reads exactly this name.
5. Add a test in `tests/` for any logic that does not need a display (command building, parsing).
6. Run `.venv/bin/python -m pytest`, then start the app and check the new sidebar entry.

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

    def create_widget(self, ctx: PluginContext) -> QWidget:
        widget = QWidget()
        QVBoxLayout(widget).addWidget(QLabel("Hallo"))
        return widget


PLUGIN = HelloPlugin()
```
