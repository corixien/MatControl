# MatControl

Small control center for a Linux (Fedora/KDE) desktop. One window plus tray icon, one plugin per function.

Planned plugins:

- Audio: pick output devices, combine them into one sink, remember the selection, per-device volume
- Network: restart NetworkManager with one click (for LTE sticks)
- Update: run a configurable "update everything" command with a live log

Root commands run through `pkexec` (Polkit password dialog). The UI is German and follows the KDE theme.

## Run

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m matcontrol
```

`--minimized` starts in the tray only. Config lives in `~/.config/matcontrol/config.json`.

## Test

```bash
.venv/bin/python -m pytest
```

## Add a function

See [HOWTOADDAFUNCTION.md](HOWTOADDAFUNCTION.md).
