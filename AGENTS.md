# AGENTS.md

MatControl: Python 3 + PySide6 control center (tray popup that slides down under the top panel) for Fedora/KDE. Home page of Samsung-style tiles, one plugin per tile. UI language German. Public repo, no secrets.

## Commands

- Setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run: `.venv/bin/python -m matcontrol` (`--minimized` = tray only, `--window` = normal window, `MATCONTROL_LOAD_EXAMPLE=1` = show the example tile)
- KWin placement script: `kwin/install.sh` (`--uninstall`); positions the popup top right under the panel
- Test: `.venv/bin/python -m pytest` (headless, `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py`)

## Layout

- `matcontrol/app.py` entry, tray. `window.py` popup window, slide animation, home grid + detail pages. `widgets.py` animated Tile, Switch, Button, IconButton, DetailPage, PageStack, Fader. `theme.py` colors (base color #1a242f, all other colors derived from its hue) + stylesheet. `config.py` JSON config. `plugin_base.py` API. `plugin_loader.py` discovery.
- `matcontrol/plugins/*.py` one plugin each; `_`-prefixed files are ignored (`_example.py` is the template).
- Adding a function: follow `HOWTOADDAFUNCTION.md`. Do not edit core files for that.

## Conventions

- Root actions via `pkexec`, never `sudo`, never stored passwords.
- External commands via `QProcess`; other blocking work (pulse, sockets) via `tasks.run_in_thread`. UI thread never blocks.
- Tests that wait on worker threads use `tests/conftest.py:wait`, not `QTest.qWait` (it starves threads).
- Everything animates (Fader); colors only from `theme.py`; flat tones, no gradients.
- Settings only through `ctx.settings` / `ctx.save()`.
- No scope creep: no linter, no packaging, no new framework unless asked.

## Roadmap

1. Skeleton, tray, plugin loader (done)
1b. Audio Split plugin (done): `plugins/audiosplit.py`, backend `audio_backend.py` (pulsectl, combine-sink `matcontrol_split`)
2. Network plugin (NetworkManager restart via pkexec)
3. Update plugin (configurable command, live log)
4. `install.sh`, `.desktop` entry, autostart
