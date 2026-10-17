"""NetworkManager state for the Network plugin (read-only, no root)."""

import subprocess

STATE_TEXT = {
    "connected": "Verbunden",
    "connecting": "Verbindet …",
    "disconnecting": "Trennt …",
    "disconnected": "Getrennt",
    "asleep": "Netzwerk aus",
}


def describe_state(raw: str) -> str:
    """German label for `nmcli -t -f STATE general` output; unknown values are shown as they are."""
    state = raw.strip().lower()
    for key, text in STATE_TEXT.items():
        if state == key or state.startswith(key + " "):
            return text
    return state.capitalize() if state else "Unbekannt"


def current_state() -> str:
    """Raw NetworkManager state; raises when NetworkManager cannot be queried."""
    result = subprocess.run(
        ["nmcli", "-t", "-f", "STATE", "general"], capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr.strip().splitlines() or ["nmcli Fehler"])[-1])
    return result.stdout.strip()
