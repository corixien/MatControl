# Project Resume

> Instruction for Claude: read this whole file first. Then read every file under "Must read before any change". Do not modify anything until you have fully understood the project. Keep this file updated as you work (see "Maintenance rules").

Last updated: 2026-10-21

## 1. What this project is
MatControl: Python 3 + PySide6 control center for Fedora/KDE (Plasma 6, Wayland). A tray popup slides down under the top panel; the home page is a 4-column grid of Samsung-style tiles, one plugin per tile (click icon = on/off, click beside = details). Dark flat theme derived from base color #1a242f, everything animates. UI language German. Public repo `corixien/MatControl`, no secrets.
Plugins, all done: Usage (2x1 under System: weekly Claude limit % + daily target (14.3 % x started days since the reset) "Soll N %" from the undocumented `api.anthropic.com/api/oauth/usage` endpoint using the Claude Code OAuth token in `~/.claude/.credentials.json`, read-only; click opens `claude-desktop`), System (view-only 2x2 tile top right: CPU, RAM, network; click opens the system monitor), Audio Split (play audio on several outputs, volume + delay in ms per device), Update (dnf + flatpak check, update command via pkexec with live log), Network (restart NetworkManager via pkexec, shows connection state).
The program is installed for the user (`./install.sh`): launcher `~/.local/bin/matcontrol`, menu entry, autostart (hidden in tray), KWin placement script.

## 2. Must read before any change
1. `AGENTS.md` - commands, layout, conventions, roadmap, git push recipe.
2. `README.md` - user-facing description, install.
3. `HOWTOADDAFUNCTION.md` - how to add a plugin (never edit core files for that).
4. `matcontrol/plugin_base.py`, `matcontrol/plugin_loader.py` - plugin API (tile_active/attention/subtitle, toggle, create_tile, tile_cells, tile_pin, has_detail, tile_clicked) and discovery.
5. `matcontrol/window.py`, `matcontrol/widgets.py`, `matcontrol/theme.py` - popup + slide animation + grid placement, animated widgets, colors.
6. `tests/conftest.py` - headless Qt setup, `wait` helper, GC handling.

## 3. How to navigate
- `matcontrol/app.py` entry, tray (icon as pixmaps without theme name), single instance via local socket `/tmp/matcontrol`; `__main__.py` CLI (`--minimized`, `--window`).
- `matcontrol/plugins/*.py` one plugin each (`_`-prefixed ignored; `_example.py` = template): `system.py` (+ `sysstats.py`), `audiosplit.py` (+ `audio_backend.py`: pulsectl, null-sink `matcontrol_split`, one loopback per device, loopback latency = delay), `update.py` (+ `updates.py`), `network.py` (+ `matcontrol/network.py`), `usage.py` (+ `matcontrol/usage.py`).
- `matcontrol/runner.py` CommandRunner (pkexec, live output) shared by Update and Network. `matcontrol/tasks.py` `run_in_thread` for blocking work. `matcontrol/config.py` JSON config (`~/.config/matcontrol`), settings only via `ctx.settings` / `ctx.save()`.
- `kwin/matcontrol-popup/` KWin script (places the popup `GAP_TOP` px under the top panel, found via the plasmashell dock window); `kwin/install.sh` installs and reloads it. `install.sh` installs launcher, `.desktop`, autostart, icon (`matcontrol/data/matcontrol.svg`).

## 4. Commands
Run from `~/MatControl`.
- Setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run: `.venv/bin/python -m matcontrol`
- Test: `.venv/bin/python -m pytest` (headless, 90 tests).
- Install as program: `./install.sh` (`--uninstall`, `--no-autostart`, `--no-kwin`, `--no-deps`).
- Restart the running instance after code changes: `pkill -f "[p]ython -m matcontrol"; setsid -f ~/.local/bin/matcontrol --minimized`. After editing the KWin script run `kwin/install.sh` (KWin does not reload an upgraded script by itself).
- Push: straight to `main`, never PRs: `git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin main` (the stored libsecret credential is stale).

## 5. Invariants and gotchas
- Root actions via `pkexec`, never `sudo`, no stored passwords.
- External commands via `QProcess`; other blocking work via `tasks.run_in_thread`; UI thread never blocks.
- Tests waiting on worker threads/processes use `conftest.wait`, not `QTest.qWait`; conftest disables auto GC (GC in a worker thread crashes the event loop).
- Everything animates (Fader); colors only from `theme.py`; flat tones, no gradients.
- Labels with changing text use `QSizePolicy.Ignored` horizontally (else tiles resize every update); no horizontal scrolling; scrollbars hidden.
- Tray icon must be pixmaps without a theme name; desktop entries use the absolute icon path (the panel's icon theme did not resolve the name).
- Never `pkill -f "python -m matcontrol"` without the bracket trick, it kills the calling shell.
- No scope creep: no linter, no packaging, no new framework unless asked.

## 6. Current state
Branch `main`, clean and pushed. All four plugins and the install-as-program work are finished. The user said the app still has small unspecified bugs: ask which ones before guessing. Nothing else planned.

## Maintenance rules
Update this file when structure, commands, invariants or state change. Bump "Last updated".
