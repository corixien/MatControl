import importlib
import logging
import os
import pkgutil

from . import plugins as plugins_pkg
from .plugin_base import Plugin

log = logging.getLogger(__name__)


def discover() -> tuple[list[Plugin], list[str]]:
    """Import every non-underscore module in matcontrol/plugins and collect its PLUGIN.

    MATCONTROL_LOAD_EXAMPLE=1 also loads the _example template, for trying out the UI.
    A broken plugin never crashes the app; it is reported in the returned error list.
    """
    found: dict[str, Plugin] = {}
    errors: list[str] = []
    include_example = os.environ.get("MATCONTROL_LOAD_EXAMPLE") == "1"
    for info in pkgutil.iter_modules(plugins_pkg.__path__):
        if info.name.startswith("_") and not (include_example and info.name == "_example"):
            continue
        try:
            module = importlib.import_module(f"{plugins_pkg.__name__}.{info.name}")
            plugin = module.PLUGIN
            if not isinstance(plugin, Plugin) or not plugin.id or not plugin.name:
                raise ValueError("PLUGIN must be a Plugin instance with id and name")
            if plugin.id in found:
                raise ValueError(f"duplicate plugin id {plugin.id!r}")
            found[plugin.id] = plugin
        except Exception as exc:
            log.exception("plugin %s failed to load", info.name)
            errors.append(f"{info.name}: {exc}")
    ordered = sorted(found.values(), key=lambda p: (p.order, p.name))
    return ordered, errors
