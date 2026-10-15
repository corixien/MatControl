# AGENTS.md

MatControl: Python 3 + PySide6 control center (tray popup that slides down under the top panel) for Fedora/KDE. Home page of Samsung-style tiles, one plugin per tile. UI language German. Public repo, no secrets.

## Commands

- Setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run: `.venv/bin/python -m matcontrol` (`--minimized` = tray only, `--window` = normal window, `MATCONTROL_LOAD_EXAMPLE=1` = show the example tile)
- KWin placement script: `kwin/install.sh` (`--uninstall`); positions the popup top right under the panel
- Test: `.venv/bin/python -m pytest` (headless, `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py`)

## Layout

- `matcontrol/app.py` entry, tray. `window.py` popup window, slide animation, home grid + detail pages. `widgets.py` Tile, Switch, DetailPage. `config.py` JSON config. `plugin_base.py` API. `plugin_loader.py` discovery.
- `matcontrol/plugins/*.py` one plugin each; `_`-prefixed files are ignored (`_example.py` is the template).
- Adding a function: follow `HOWTOADDAFUNCTION.md`. Do not edit core files for that.

## Conventions

- Root actions via `pkexec`, never `sudo`, never stored passwords.
- External commands via `QProcess`, UI thread never blocks.
- Settings only through `ctx.settings` / `ctx.save()`.
- No scope creep: no linter, no packaging, no new framework unless asked.

## Roadmap

1. Skeleton, tray, plugin loader (done)
2. Network plugin (NetworkManager restart via pkexec)
3. Update plugin (configurable command, live log)
4. Audio plugin (combine sinks, remember, per-device volume; needs `pulsectl`)
5. `install.sh`, `.desktop` entry, autostart
