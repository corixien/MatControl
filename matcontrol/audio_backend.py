"""PipeWire/PulseAudio access for the Audio Split plugin (via pulsectl).

The split is a virtual output (null sink) whose monitor is looped back to every chosen
device. Each loopback has its own latency, which is how a device is delayed to line up
with a slower one (e.g. wired speakers vs. Bluetooth).

Every call opens its own short connection, so these functions are safe to run in a
worker thread (see tasks.run_in_thread).
"""

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass

import pulsectl

SINK_NAME = "matcontrol_split"  # the virtual output created by enable()
DESCRIPTION = "Audio Split"  # how it appears in the system sound menu
APP_NAME = "matcontrol"
NULL_MODULE = "module-null-sink"
LOOPBACK_MODULE = "module-loopback"
LEGACY_COMBINE_MODULE = "module-combine-sink"  # used by earlier versions, still cleaned up
BASE_LATENCY_MS = 50  # latency of the least delayed device
MAX_DELAY_MS = 600


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


def _split_modules(pulse) -> list:
    """All modules that belong to the split, loopbacks first (unload order)."""
    loopbacks, others = [], []
    for module in pulse.module_list():
        argument = module.argument or ""
        if module.name == LOOPBACK_MODULE and f"source={SINK_NAME}.monitor" in argument:
            loopbacks.append(module)
        elif module.name in (NULL_MODULE, LEGACY_COMBINE_MODULE) and f"sink_name={SINK_NAME}" in argument:
            others.append(module)
    return loopbacks + others


def _load_loopback(pulse, device: str, delay_ms: int) -> None:
    latency = BASE_LATENCY_MS + max(0, min(MAX_DELAY_MS, int(delay_ms)))
    pulse.module_load(
        LOOPBACK_MODULE,
        f"source={SINK_NAME}.monitor sink={device} latency_msec={latency} "
        "source_dont_move=true sink_dont_move=true",
    )


def _unload_all(pulse) -> None:
    for module in _split_modules(pulse):
        pulse.module_unload(module.index)


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


def enable(delays: dict[str, int]) -> str | None:
    """Play the system audio on every device in `delays` (name -> extra delay in ms).

    Creates the virtual output, loops it back to each device and makes it the default.
    Rebuilds everything if the split already exists. Returns the default output from
    before (None if the split already was the default), for disable() to restore.
    """
    if not delays:
        raise AudioError("Kein Gerät ausgewählt")
    with _connect() as pulse:
        current = pulse.server_info().default_sink_name
        previous = None if current == SINK_NAME else current
        _unload_all(pulse)
        pulse.module_load(
            NULL_MODULE,
            f"sink_name={SINK_NAME} sink_properties=\"device.description='{DESCRIPTION}'\" channels=2",
        )
        for _ in range(40):
            if any(s.name == SINK_NAME for s in pulse.sink_list()):
                break
            time.sleep(0.05)
        else:
            raise AudioError("Virtuelles Gerät wurde nicht erstellt")
        for device, delay in delays.items():
            _load_loopback(pulse, device, delay)
        pulse.sink_default_set(SINK_NAME)
        return previous


def set_delay(device: str, delay_ms: int) -> None:
    """Change the delay of one device while the split runs (only that device glitches briefly)."""
    pattern = re.compile(rf"(?:^| )sink={re.escape(device)}(?: |$)")
    with _connect() as pulse:
        if not any(s.name == SINK_NAME for s in pulse.sink_list()):
            return
        for module in _split_modules(pulse):
            if module.name == LOOPBACK_MODULE and pattern.search(module.argument or ""):
                pulse.module_unload(module.index)
        _load_loopback(pulse, device, delay_ms)


def disable(restore: str | None) -> None:
    """Remove the split; make `restore` the default again if it still exists."""
    with _connect() as pulse:
        if restore and any(s.name == restore for s in pulse.sink_list()):
            pulse.sink_default_set(restore)
        _unload_all(pulse)


def set_volume(name: str, value: float) -> None:
    with _connect() as pulse:
        try:
            sink = pulse.get_sink_by_name(name)
        except pulsectl.PulseIndexError as exc:
            raise AudioError("Gerät nicht mehr vorhanden") from exc
        pulse.volume_set_all_chans(sink, max(0.0, min(1.0, value)))
