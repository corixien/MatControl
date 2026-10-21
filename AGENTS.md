# AGENTS.md

MatControl: Python 3 + PySide6 control center (tray popup that slides down under the top panel) for Fedora/KDE. Home page of Samsung-style tiles, one plugin per tile. UI language German. Public repo (`corixien/MatControl`), no secrets.

## Commands

- Setup: `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run: `.venv/bin/python -m matcontrol` (`--minimized` = tray only, `--window` = normal window)
- Test: `.venv/bin/python -m pytest` (headless, `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py`)
- Install as program: `./install.sh` (`--uninstall`, `--no-autostart`, `--no-kwin`, `--no-deps`): launcher `~/.local/bin/matcontrol`, `.desktop` + autostart entries (absolute icon path), icon, KWin script. After code changes the running instance must be restarted: `pkill -f "[p]ython -m matcontrol"` (the bracket keeps the pattern from matching the calling shell), then `setsid -f ~/.local/bin/matcontrol --minimized`.
- KWin placement script: `kwin/install.sh` (`--uninstall`). Puts the popup top right, `GAP_TOP` px under the top panel. It swaps the running script (KWin does not reload an upgraded one by itself), so rerun it after every edit of `kwin/matcontrol-popup/contents/code/main.js`.
- Git: push straight to `main`, never open PRs. The stored libsecret credential is stale, so push with `git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin main`.

## Layout

- `matcontrol/app.py` entry, tray (icon as pixmaps, no theme name), single instance via local socket `/tmp/matcontrol`. `window.py` popup window, slide animation, 4-column home grid (`place_tiles`) + detail pages. `widgets.py` animated Card, Tile, Switch, Slider, Button, IconButton, DetailPage, PageStack, Fader. `theme.py` colors (base color #1a242f, all other colors derived from its hue) + stylesheet. `plugin_base.py` plugin API. `plugin_loader.py` discovery. `config.py` JSON config. `tasks.py` `run_in_thread`. `runner.py` CommandRunner (pkexec + live output, shared by Update and Network). `sysstats.py` /proc parsing + Sampler. `data/matcontrol.svg` app icon.
- `matcontrol/plugins/*.py` one plugin each; `_`-prefixed files are ignored (`_example.py` is the template):
  - `system.py` view-only 2x2 tile top right (CPU, RAM, network), no detail page, click opens the system monitor.
  - `audiosplit.py` + `audio_backend.py` (pulsectl; null-sink `matcontrol_split` + one loopback per device, loopback latency = per-device delay).
  - `update.py` + `updates.py` (dnf check-update + flatpak; command via `pkexec sh -c` with live log).
  - `network.py` + helper module `matcontrol/network.py` (nmcli state; restart = `systemctl stop NetworkManager; systemctl start NetworkManager` via pkexec).
  - `usage.py` + `matcontrol/usage.py` 2x1 tile (order 40, flows into the cell under System), weekly Claude limit and even-pace target ("Soll N %") from `api.anthropic.com/api/oauth/usage` with the Claude Code OAuth token (read only, never refreshed/stored/logged), fetch in a worker thread at most every 5 min, click opens `claude-desktop`.
- Adding a function: follow `HOWTOADDAFUNCTION.md`. Do not edit core files for that.

## Conventions

- Root actions via `pkexec`, never `sudo`, never stored passwords.
- External commands via `QProcess`; other blocking work (pulse, sockets, dnf) via `tasks.run_in_thread`. UI thread never blocks.
- Tests that wait on worker threads use `tests/conftest.py:wait`, not `QTest.qWait` (it starves threads). `conftest` also disables automatic GC and collects between tests: GC inside a worker thread destroys Qt objects from the wrong thread and crashes the event loop.
- Everything animates (Fader); colors only from `theme.py`; flat tones, no gradients.
- Layout stability: labels whose text changes (values, status lines) use `QSizePolicy.Ignored` horizontally, otherwise the text width resizes the tiles every update. No horizontal scrolling anywhere; scrollbars are hidden (wheel scrolling only, and only when the content does not fit).
- Settings only through `ctx.settings` / `ctx.save()`.
- No scope creep: no linter, no packaging, no new framework unless asked.

## Roadmap

Done: skeleton, tray, plugin loader; Audio Split (with per-device delay); Update; Network; System tile, Claude usage tile; install as program (launcher, menu entry, autostart, icon); popup gap and KWin placement.
Open: nothing planned. Known: the user reported unspecified small bugs, ask which ones.
