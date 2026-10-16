"""Audio Split: play the system audio on several output devices at once.

Tile: on/off and status. Detail page: choose the devices (switch per device), set the volume
of each device (slider) and delay a device in ms (second slider) so devices with different
latency, e.g. wired vs. Bluetooth, play in sync. Needs PipeWire or PulseAudio.
"""

import time

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .. import audio_backend as audio
from .. import theme
from ..plugin_base import Plugin, PluginContext
from ..tasks import run_in_thread
from ..widgets import Slider, Switch

MIN_DEVICES = 2
STALE_S = 2.0  # tile state older than this is refreshed in the background
POLL_MS = 1500  # detail page: pick up external volume/device changes
VOLUME_THROTTLE_MS = 50
DELAY_SETTLE_MS = 300  # apply a delay change this long after the last slider move (it glitches the device)
DELAY_STEP_MS = 5
TOUCH_HOLD_S = 2.0  # after a user volume change, ignore server values this long (they lag behind)


class AudioSplitPlugin(Plugin):
    id = "audiosplit"
    name = "Audio Split"
    icon = "audio-speakers"
    order = 10

    def __init__(self) -> None:
        self.snapshot: audio.Snapshot | None = None
        self.error: str | None = None
        self._fetched_at = 0.0
        self._fetching = False
        self._busy = False
        self._target = False
        self._dirty = False  # selection changed while busy: re-apply afterwards

    # state shared by tile and detail page

    def selected(self, ctx: PluginContext) -> list[str]:
        return list(ctx.settings.get("selected", []))

    def valid_selected(self, ctx: PluginContext) -> list[str]:
        present = {d.name for d in self.snapshot.devices} if self.snapshot else set()
        return [name for name in self.selected(ctx) if name in present]

    def delay_of(self, ctx: PluginContext, name: str) -> int:
        return int(ctx.settings.get("delays", {}).get(name, 0))

    def refresh(self, ctx: PluginContext) -> None:
        """Fetch the audio state in the background; notifies when it changed."""
        if self._fetching:
            return
        self._fetching = True
        run_in_thread(audio.snapshot, lambda result, error: self.on_snapshot(ctx, result, error))

    def on_snapshot(self, ctx: PluginContext, result: audio.Snapshot | None, error: Exception | None) -> None:
        self._fetching = False
        self._fetched_at = time.monotonic()
        before = (self.snapshot, self.error)
        if error is not None:
            self.error = str(error)
        else:
            self.snapshot, self.error = result, None
        if (self.snapshot, self.error) != before:
            ctx.notify_changed()

    # tile

    def tile_active(self, ctx: PluginContext) -> bool | None:
        if time.monotonic() - self._fetched_at > STALE_S:
            self.refresh(ctx)
        if self._busy:
            return self._target
        return bool(self.snapshot and self.snapshot.active)

    def tile_subtitle(self, ctx: PluginContext) -> str:
        if self.error:
            return "Audio nicht verfügbar"
        if self._busy:
            return "Wird umgeschaltet …"
        count = len(self.valid_selected(ctx))
        if self.snapshot and self.snapshot.active:
            return f"Aktiv auf {count} Geräten"
        if count < MIN_DEVICES:
            return "2 Geräte wählen"
        return f"Aus · {count} Geräte gewählt"

    def toggle(self, ctx: PluginContext) -> None:
        if self._busy:
            return
        active = bool(self.snapshot and self.snapshot.active)
        if not active and len(self.valid_selected(ctx)) < MIN_DEVICES:
            return  # the detail page explains what is missing
        self._apply(ctx, target=not active)

    # actions

    def set_selected(self, ctx: PluginContext, name: str, on: bool) -> None:
        names = [n for n in self.selected(ctx) if n != name]
        if on:
            names.append(name)
        ctx.settings["selected"] = names
        ctx.save()
        ctx.notify_changed()
        if self.snapshot and self.snapshot.active:
            if self._busy:
                self._dirty = True
            else:
                self._reapply(ctx)

    def set_delay(self, ctx: PluginContext, name: str, delay_ms: int) -> None:
        """Store the delay of one device and apply it live when the split is on."""
        ctx.settings.setdefault("delays", {})[name] = delay_ms
        ctx.save()
        if not (self.snapshot and self.snapshot.active):
            return
        if self._busy:
            self._dirty = True  # the re-apply after the running change uses the stored delays
        elif name in self.valid_selected(ctx):
            run_in_thread(audio.set_delay, lambda r, e: self._delay_applied(ctx, e), name, delay_ms)

    def _delay_applied(self, ctx: PluginContext, error: Exception | None) -> None:
        if error is not None:
            self.error = str(error)
            ctx.notify_changed()

    def _reapply(self, ctx: PluginContext) -> None:
        """Selection changed while the split is on: rebuild it, or switch off when nothing is left."""
        self._apply(ctx, target=bool(self.valid_selected(ctx)))

    def _apply(self, ctx: PluginContext, target: bool) -> None:
        self._busy = True
        self._target = target
        ctx.notify_changed()
        if target:
            delays = {name: self.delay_of(ctx, name) for name in self.valid_selected(ctx)}
            run_in_thread(audio.enable, lambda r, e: self._applied(ctx, r, e), delays)
        else:
            run_in_thread(audio.disable, lambda r, e: self._applied(ctx, r, e), ctx.settings.get("previous_default"))

    def _applied(self, ctx: PluginContext, previous: str | None, error: Exception | None) -> None:
        self._busy = False
        self.error = str(error) if error is not None else None
        if self._target and previous:
            ctx.settings["previous_default"] = previous
            ctx.save()
        if self._dirty:
            self._dirty = False
            self._reapply(ctx)
            return
        self._fetched_at = 0.0
        self.refresh(ctx)
        ctx.notify_changed()

    # detail page

    def create_widget(self, ctx: PluginContext) -> QWidget:
        return AudioSplitPage(self, ctx)


class DeviceRow(QFrame):
    """One output device: name + select switch on top, volume slider below."""

    def __init__(self, device: audio.Device, selected: bool, delay_ms: int):
        super().__init__()
        self.name = device.name
        self.setMinimumHeight(128)

        title = QLabel(device.description)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        font = title.font()
        font.setBold(True)
        title.setFont(font)

        self.switch = Switch()
        self.switch.setChecked(selected)
        self.slider = Slider()
        self.percent = QLabel()
        self.percent.setFixedWidth(56)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        palette = self.percent.palette()
        palette.setColor(self.percent.foregroundRole(), theme.TEXT_DIM)
        self.percent.setPalette(palette)
        self.slider.valueChanged.connect(lambda v: self.percent.setText(f"{v}%"))
        self.set_volume(device.volume)
        self.percent.setText(f"{self.slider.value()}%")

        self.delay_slider = Slider()
        self.delay_slider.setRange(0, audio.MAX_DELAY_MS)
        self.delay_slider.setSingleStep(DELAY_STEP_MS)
        self.delay_value = QLabel()
        self.delay_value.setFixedWidth(56)
        self.delay_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.delay_value.setPalette(palette)
        self.delay_slider.valueChanged.connect(lambda v: self.delay_value.setText(f"{v} ms"))
        self.delay_slider.setValue(delay_ms)
        self.delay_value.setText(f"{delay_ms} ms")
        delay_title = QLabel("Verzögerung")
        delay_title.setPalette(palette)
        delay_title.setFixedWidth(80)
        volume_title = QLabel("Lautstärke")
        volume_title.setPalette(palette)
        volume_title.setFixedWidth(80)

        top = QHBoxLayout()
        top.addWidget(title, 1)
        top.addWidget(self.switch)
        bottom = QHBoxLayout()
        bottom.addWidget(volume_title)
        bottom.addWidget(self.slider, 1)
        bottom.addWidget(self.percent)
        delay = QHBoxLayout()
        delay.addWidget(delay_title)
        delay.addWidget(self.delay_slider, 1)
        delay.addWidget(self.delay_value)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        layout.addLayout(top)
        layout.addLayout(bottom)
        layout.addLayout(delay)

    def set_volume(self, volume: float) -> None:
        self.slider.setValue(round(max(0.0, min(1.0, volume)) * 100))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.SURFACE)
        p.drawRoundedRect(QRectF(self.rect()), 14, 14)

    def sizeHint(self) -> QSize:
        return QSize(300, 128)


class AudioSplitPage(QWidget):
    def __init__(self, plugin: AudioSplitPlugin, ctx: PluginContext):
        super().__init__()
        self.plugin = plugin
        self.ctx = ctx
        self.rows: dict[str, DeviceRow] = {}
        self._pending: dict[str, float] = {}
        self._touched: dict[str, float] = {}
        self._delay_pending: dict[str, int] = {}
        self._fetching = False

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        palette = self.hint.palette()
        palette.setColor(self.hint.foregroundRole(), theme.TEXT_DIM)
        self.hint.setPalette(palette)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addLayout(self.list_layout)
        container_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # wheel scrolling only
        scroll.setWidget(container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.hint)
        layout.addWidget(scroll, 1)

        self.volume_timer = QTimer(self)
        self.volume_timer.setSingleShot(True)
        self.volume_timer.setInterval(VOLUME_THROTTLE_MS)
        self.volume_timer.timeout.connect(self._flush_volumes)
        self.delay_timer = QTimer(self)
        self.delay_timer.setSingleShot(True)
        self.delay_timer.setInterval(DELAY_SETTLE_MS)
        self.delay_timer.timeout.connect(self._flush_delays)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_MS)
        self.poll_timer.timeout.connect(self._poll)
        ctx.changed.connect(self._update_hint)
        self._sync()

    def showEvent(self, event) -> None:
        self._poll()
        self.poll_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.poll_timer.stop()
        super().hideEvent(event)

    def _poll(self) -> None:
        if self._fetching:
            return
        self._fetching = True
        run_in_thread(audio.snapshot, self._polled)

    def _polled(self, result: audio.Snapshot | None, error: Exception | None) -> None:
        self._fetching = False
        self.plugin.on_snapshot(self.ctx, result, error)
        self._sync()

    def _sync(self) -> None:
        snapshot = self.plugin.snapshot
        devices = snapshot.devices if snapshot else ()
        if [d.name for d in devices] != list(self.rows):
            self._rebuild(devices)
        else:
            for device in devices:
                row = self.rows[device.name]
                held = time.monotonic() - self._touched.get(device.name, 0.0) < TOUCH_HOLD_S
                if not row.slider.isSliderDown() and not held:
                    row.set_volume(device.volume)
        self._update_hint()

    def _rebuild(self, devices) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows.clear()
        selected = set(self.plugin.selected(self.ctx))
        for device in devices:
            row = DeviceRow(device, device.name in selected, self.plugin.delay_of(self.ctx, device.name))
            row.switch.clicked.connect(lambda checked, name=device.name: self.plugin.set_selected(self.ctx, name, checked))
            row.slider.user_changed.connect(lambda value, name=device.name: self._volume_changed(name, value))
            row.delay_slider.user_changed.connect(lambda value, name=device.name: self._delay_changed(name, value))
            self.list_layout.addWidget(row)
            self.rows[device.name] = row

    def _update_hint(self) -> None:
        plugin = self.plugin
        if plugin.error:
            text = f"Audio-Server nicht erreichbar: {plugin.error}"
        elif plugin.snapshot and not plugin.snapshot.devices:
            text = "Keine Ausgabegeräte gefunden."
        elif not (plugin.snapshot and plugin.snapshot.active) and len(plugin.valid_selected(self.ctx)) < MIN_DEVICES:
            text = "Wähle mindestens zwei Geräte, dann oben den Schalter umlegen."
        else:
            text = ""
        self.hint.setText(text)
        self.hint.setVisible(bool(text))

    def _volume_changed(self, name: str, value: int) -> None:
        self._pending[name] = value / 100
        self._touched[name] = time.monotonic()
        if not self.volume_timer.isActive():
            self.volume_timer.start()

    def _delay_changed(self, name: str, value: int) -> None:
        self._delay_pending[name] = value
        self.delay_timer.start()  # restarts: applies once the slider stopped moving

    def _flush_delays(self) -> None:
        pending, self._delay_pending = self._delay_pending, {}
        for name, value in pending.items():
            self.plugin.set_delay(self.ctx, name, value)

    def _flush_volumes(self) -> None:
        pending, self._pending = self._pending, {}
        for name, volume in pending.items():
            run_in_thread(audio.set_volume, lambda r, e: None, name, volume)


PLUGIN = AudioSplitPlugin()
