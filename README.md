# MatControl

Small control center for a Linux (Fedora/KDE) desktop. Tray popup that slides down from the top panel: a home page of tiles, one per function. Click a tile icon to switch it on/off, click beside it for the details and settings (like Samsung quick settings). Dark theme from one base color (`#1a242f`), everything animates.

Plugins (all done):

- System: view-only 2x2 tile in the top-right corner with live CPU, RAM and network speed. A click opens the system monitor (`plasma-systemmonitor`, falls back to ksysguard / gnome-system-monitor / missioncenter).
- Audio Split: play the system audio on several output devices at once; choose the devices, volume slider per device. Creates one virtual output, loops it back to every chosen device and makes it the default; switching off restores the previous default. Per device a delay in ms (loopback latency) lines up devices with different latency, e.g. wired and Bluetooth.
- Update: checks dnf and flatpak for pending updates (icon tinted when there are some). Click the icon to run a configurable update command as root (Polkit dialog) with a live log; the icon stays inverted while it runs. Default: `dnf upgrade -y`, `flatpak update -y`, `fwupdmgr update -y`.
- Network: shows the connection state; click the icon to restart NetworkManager (stop, then start) as root (Polkit dialog), e.g. after plugging in an LTE stick. The icon stays inverted until both commands are done.
- Claude Nutzung: 2x1 tile under the System tile with the weekly Claude limit used so far (claude.ai and Claude Code together) and the daily target (14.3 % per started day of the week, counted from the weekly reset) to see whether you are on track. Data from Anthropic's usage endpoint (`api.anthropic.com/api/oauth/usage`, undocumented, queried at most every 5 minutes) with the OAuth token Claude Code keeps in `~/.claude/.credentials.json` (read-only, not refreshed here: shows "Token abgelaufen" until Claude Code renewed it). A click opens Claude Desktop (`claude-desktop`).

Root commands run through `pkexec` (Polkit password dialog), never `sudo`. The UI is German.

## Install as a program

```bash
./install.sh              # launcher ~/.local/bin/matcontrol, app-menu entry, icon, autostart, KWin script
./install.sh --uninstall  # remove everything (config in ~/.config/matcontrol stays)
```

Options: `--no-autostart`, `--no-kwin`, `--no-deps`. Per user, no root. After installing, start MatControl from the app menu or run `matcontrol`; at login it starts hidden in the tray. A second launch only opens the popup of the running instance. Re-run `install.sh` if you move the repo, and restart the running instance after updating the code.

## Run from the repo (development)

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m matcontrol
```

`--minimized` starts in the tray only, `--window` opens a normal decorated window instead of the popup. Config lives in `~/.config/matcontrol/config.json`.

## Panel popup (KDE Plasma 6, Wayland)

By default the window is a frameless popup that closes when it loses focus. Wayland apps cannot position their own windows, so a small KWin script places it at the top right, a few pixels under the top panel (`GAP_TOP` in `kwin/matcontrol-popup/contents/code/main.js`):

```bash
kwin/install.sh              # install, enable and (re)load it (per user, no root)
kwin/install.sh --uninstall  # remove
```

Without the script the popup still works, but KWin picks its position.

## Test

```bash
.venv/bin/python -m pytest
```

## Add a function

See [HOWTOADDAFUNCTION.md](HOWTOADDAFUNCTION.md).
