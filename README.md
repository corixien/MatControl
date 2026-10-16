# MatControl

Small control center for a Linux (Fedora/KDE) desktop. Tray popup that slides down from the top panel: a home page of tiles, one per function. Click a tile icon to switch it on/off, click beside it for the details and settings (like Samsung quick settings).

Plugins:

- Audio Split (done): play the system audio on several output devices at once, choose the devices, volume slider per device. Creates one virtual output, loops it back to every chosen device and makes it the default; switching off restores the previous default. Per device a delay in ms (loopback latency) lines up devices with different latency, e.g. wired and Bluetooth.

- Update (done): checks dnf and flatpak for pending updates (icon tinted when there are some), click the icon to run a configurable update command as root (Polkit dialog) with a live log; the icon stays inverted while it runs. Default: `dnf upgrade -y`, `flatpak update -y`, `fwupdmgr update -y`.

Planned:

- Network: restart NetworkManager with one click (for LTE sticks)

Root commands run through `pkexec` (Polkit password dialog). The UI is German and follows the KDE theme.

## Install as a program

```bash
./install.sh              # launcher ~/.local/bin/matcontrol, app-menu entry, icon, autostart, KWin script
./install.sh --uninstall  # remove everything (config in ~/.config/matcontrol stays)
```

Options: `--no-autostart`, `--no-kwin`, `--no-deps`. Per user, no root. After installing, start MatControl from the app menu or run `matcontrol`; at login it starts hidden in the tray. A second launch only opens the popup of the running instance. Re-run `install.sh` if you move the repo.

## Run from the repo (development)

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
