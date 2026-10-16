"""PipeWire/PulseAudio access for the Audio Split plugin (via pulsectl).

Every call opens its own short connection, so these functions are safe to run in a
worker thread (see tasks.run_in_thread).
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass

import pulsectl

SINK_NAME = "matcontrol_split"  # the combined output created by enable()
DESCRIPTION = "Audio Split"  # how it appears in the system sound menu
APP_NAME = "matcontrol"
COMBINE_MODULE = "module-combine-sink"


class AudioError(Exception):
    """Audio server unreachable or an operation failed. Message is shown to the user."""


@dataclass(frozen=True)
class Device:
    name: str
    description: str
    volume: float  # 0.0 .. 1.0+ (average over channels)
    muted: bool


@dataclass(frozen=True)
class Snapshot:
    devices: tuple[Device, ...]  # real outputs only, never the combined one
    active: bool  # combined output exists
    default: str | None  # current default output name


@contextmanager
def _connect():
    try:
        with pulsectl.Pulse(APP_NAME) as pulse:
            yield pulse
    except (pulsectl.PulseError, OSError) as exc:
        raise AudioError(str(exc) or exc.__class__.__name__) from exc


def _combined_modules(pulse) -> list:
    needle = f"sink_name={SINK_NAME}"
    return [m for m in pulse.module_list() if m.name == COMBINE_MODULE and needle in (m.argument or "")]


def snapshot() -> Snapshot:
    with _connect() as pulse:
        sinks = pulse.sink_list()
        devices = tuple(
            Device(s.name, s.description, float(s.volume.value_flat), bool(s.mute))
            for s in sinks
            if s.name != SINK_NAME
        )
        active = any(s.name == SINK_NAME for s in sinks)
        return Snapshot(devices, active, pulse.server_info().default_sink_name)


def enable(names: list[str]) -> str | None:
    """Combine the given outputs into one and make it the default.

    Rebuilds the combined output if it already exists. Returns the default output from
    before (None if the combined output already was the default), for disable() to restore.
    """
    if not names:
        raise AudioError("Kein Gerät ausgewählt")
    with _connect() as pulse:
        current = pulse.server_info().default_sink_name
        previous = None if current == SINK_NAME else current
        for module in _combined_modules(pulse):
            pulse.module_unload(module.index)
        args = f"sink_name={SINK_NAME} sink_properties=\"device.description='{DESCRIPTION}'\" slaves={','.join(names)}"
        pulse.module_load(COMBINE_MODULE, args)
        for _ in range(40):
            if any(s.name == SINK_NAME for s in pulse.sink_list()):
                break
            time.sleep(0.05)
        else:
            raise AudioError("Kombiniertes Gerät wurde nicht erstellt")
        pulse.sink_default_set(SINK_NAME)
        return previous


def disable(restore: str | None) -> None:
    """Remove the combined output; make `restore` the default again if it still exists."""
    with _connect() as pulse:
        if restore and any(s.name == restore for s in pulse.sink_list()):
            pulse.sink_default_set(restore)
        for module in _combined_modules(pulse):
            pulse.module_unload(module.index)


def set_volume(name: str, value: float) -> None:
    with _connect() as pulse:
        try:
            sink = pulse.get_sink_by_name(name)
        except pulsectl.PulseIndexError as exc:
            raise AudioError("Gerät nicht mehr vorhanden") from exc
        pulse.volume_set_all_chans(sink, max(0.0, min(1.0, value)))
