# Project Resume

> Instruction for Claude: read this whole file first. Then read every file under "Must read before any change". Do not modify anything until you have fully understood the project. Keep this file updated as you work (see "Maintenance rules").

Last updated: 2026-10-16

## 1. What this project is
MatControl: Python 3 + PySide6 control center for Fedora/KDE. Tray popup slides down under the top panel; home page of Samsung-style tiles, one plugin per tile (click icon = on/off, click beside = details). UI language German. Public repo (`corixien/MatControl`), no secrets. Plugins done: Audio Split, Update. Planned: Network (NetworkManager restart for LTE sticks).

## 2. Must read before any change
1. `AGENTS.md` - commands, layout, conventions, roadmap.
2. `README.md` - user-facing description, install.
3. `HOWTOADDAFUNCTION.md` - how to add a plugin (never edit core files for that).
4. `matcontrol/plugin_base.py`, `matcontrol/plugin_loader.py` - plugin API and discovery.
5. `matcontrol/window.py`, `matcontrol/widgets.py`, `matcontrol/theme.py` - popup, animated widgets, colors.
6. `tests/conftest.py` - headless Qt setup and `wait` helper.

## 3. How to navigate
- `matcontrol/app.py` entry + tray; `__main__.py` CLI (`--minimized`, `--window`).
- `matcontrol/plugins/*.py` one plugin each (`_`-prefixed ignored; `_example.py` = template). `audiosplit.py` + `audio_backend.py` (pulsectl, null-sink `matcontrol_split`, one loopback per device). `update.py` + `updates.py` (dnf check-update + flatpak, `pkexec sh -c` with live log).
- `matcontrol/config.py` JSON config (`~/.config/matcontrol`); settings only via `ctx.settings` / `ctx.save()`.
- `matcontrol/tasks.py` `run_in_thread` for blocking work.
- `kwin/` KWin script placing the popup top right; `install.sh` installs launcher, `.desktop`, autostart, icon.
- Single instance via local socket `/tmp/matcontrol`.

## 4. Commands
Run from `~/MatControl`.
- Setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run: `.venv/bin/python -m matcontrol`
- Test: `.venv/bin/python -m pytest` (headless).
- Install as program: `./install.sh` (`--uninstall`, `--no-autostart`, `--no-kwin`, `--no-deps`). Restart running instance after code changes: `pkill -f '[p]ython -m matcontrol'`.

## 5. Invariants and gotchas
- Root actions via `pkexec`, never `sudo`, no stored passwords.
- External commands via `QProcess`; UI thread never blocks.
- Tests waiting on worker threads use `conftest.wait`, not `QTest.qWait`.
- Everything animates (Fader); colors only from `theme.py` (base #1a242f); flat tones, no gradients.
- No scope creep: no linter, no packaging, no new framework unless asked.

## 6. Current state
Branch `main`, clean. Last work: install as program, Update plugin, per-device delay in Audio Split. Next: Network plugin.

## Maintenance rules
Update this file when structure, commands, invariants or state change. Bump "Last updated".
