import json
import os
from pathlib import Path


def config_path() -> Path:
    override = os.environ.get("MATCONTROL_CONFIG_DIR")
    if override:
        return Path(override) / "config.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "matcontrol" / "config.json"


class Config:
    """JSON config; each plugin gets its own section under "plugins"."""

    def __init__(self, path: Path | None = None):
        self.path = path or config_path()
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def plugin(self, plugin_id: str) -> dict:
        """Mutable settings dict of one plugin. Call save() after changing it."""
        return self._data.setdefault("plugins", {}).setdefault(plugin_id, {})
