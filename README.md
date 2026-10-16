# MatControl

Small control center for a Linux (Fedora/KDE) desktop. Tray popup that slides down from the top panel: a home page of tiles, one per function. Click a tile icon to switch it on/off, click beside it for the details and settings (like Samsung quick settings).

Plugins:

- Audio Split (done): play the system audio on several output devices at once, choose the devices, volume slider per device. Combines the chosen outputs into one virtual device (`module-combine-sink`) and makes it the default; switching off restores the previous default.

Planned:

- Network: restart NetworkManager with one click (for LTE sticks)
- Update: run a configurable "update everything" command with a live log

Root commands run through `pkexec` (Polkit password dialog). The UI is German and follows the KDE theme.

## Run

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m matcontrol
```

`--minimized` starts in the tray only, `--window` opens a normal decorated window instead of the popup. Config lives in `~/.config/matcontrol/config.json`.

## Panel popup (KDE Plasma 6, Wayland)

By default the window is a frameless popup that closes when it loses focus. Wayland apps cannot position their own windows, so a small KWin script places it at the top right under the panel:

```bash
kwin/install.sh              # install and enable (per user, no root)
kwin/install.sh --uninstall  # remove
```

Without the script the popup still works, but KWin picks its position.

## Test

```bash
.venv/bin/python -m pytest
```

## Add a function

See [HOWTOADDAFUNCTION.md](HOWTOADDAFUNCTION.md).
