"""System: view-only 2x2 tile with CPU, RAM and network usage. A click opens the system monitor."""

import shutil

from PySide6.QtCore import QProcess, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .. import theme
from ..plugin_base import Plugin, PluginContext
from ..sysstats import Sampler, Stats, format_rate
from ..widgets import Fader

MONITORS = ("plasma-systemmonitor", "ksysguard", "gnome-system-monitor", "missioncenter")
INTERVAL_MS = 1000
FIRST_SAMPLE_MS = 300  # show numbers soon after opening instead of after a full second
MIN_NET_SCALE = 1_000_000  # bytes/s that fill the network bar at least


def find_monitor() -> str | None:
    for name in MONITORS:
        path = shutil.which(name)
        if path:
            return path
    return None


def start_detached(program: str) -> bool:
    return QProcess.startDetached(program, [])


class Meter(QWidget):
    """Thin progress bar; the fill glides to each new value."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(6)
        self.level = Fader(self, 500)

    def set_fraction(self, fraction: float) -> None:
        self.level.to(max(0.0, min(1.0, fraction)))

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2
        p.setBrush(theme.TRACK_OFF)
        p.drawRoundedRect(QRectF(self.rect()), radius, radius)
        p.setBrush(theme.ON)
        width = max(self.height(), self.width() * self.level.value) if self.level.value > 0 else 0
        p.drawRoundedRect(QRectF(0, 0, width, self.height()), radius, radius)


class MetricRow(QWidget):
    """Left text and right text on top, bar below. The labels ignore their text width: changing
    numbers must never change the width of the tile."""

    def __init__(self, left: str, dim_left: bool = True) -> None:
        super().__init__()
        self.left = QLabel(left)
        self.right = QLabel("–")
        for label in (self.left, self.right):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bold = self.right.font()
        bold.setBold(True)
        self.right.setFont(bold)
        if dim_left:
            palette = self.left.palette()
            palette.setColor(self.left.foregroundRole(), theme.TEXT_DIM)
            self.left.setPalette(palette)
        else:
            self.left.setFont(bold)
        self.meter = Meter()

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.left, 1)
        header.addWidget(self.right, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addLayout(header)
        layout.addWidget(self.meter)

    def show_value(self, text: str, fraction: float, left: str | None = None) -> None:
        self.right.setText(text)
        if left is not None:
            self.left.setText(left)
        self.meter.set_fraction(fraction)


class SystemStatsTile(QWidget):
    """Samples once a second while visible (the popup is hidden most of the time)."""

    def __init__(self, sampler: Sampler | None = None) -> None:
        super().__init__()
        self.sampler = sampler or Sampler()
        self.net_peak = float(MIN_NET_SCALE)
        self.cpu = MetricRow("CPU")
        self.ram = MetricRow("RAM")
        self.net = MetricRow("↓ –", dim_left=False)  # arrows are the titles: download left, upload right

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(self.cpu)
        layout.addStretch(1)
        layout.addWidget(self.ram)
        layout.addStretch(1)
        layout.addWidget(self.net)
        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(INTERVAL_MS)
        self.timer.timeout.connect(self.tick)

    def showEvent(self, event) -> None:
        self.sampler.reset()
        self.timer.start()
        QTimer.singleShot(FIRST_SAMPLE_MS, self.tick)
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def tick(self) -> None:
        if self.isVisible():
            self.show_stats(self.sampler.sample())

    def show_stats(self, stats: Stats) -> None:
        self.cpu.show_value(f"{stats.cpu_percent:.0f} %", stats.cpu_percent / 100)
        self.ram.show_value(f"{stats.ram_used_gb:.1f} / {stats.ram_total_gb:.1f} GB", stats.ram_percent / 100)
        self.net_peak = max(self.net_peak * 0.97, stats.rx_bytes_per_s, float(MIN_NET_SCALE))
        self.net.show_value(
            f"↑ {format_rate(stats.tx_bytes_per_s)}",
            stats.rx_bytes_per_s / self.net_peak,
            left=f"↓ {format_rate(stats.rx_bytes_per_s)}",
        )


class SystemPlugin(Plugin):
    id = "system"
    name = "System"
    order = 0
    tile_cells = (2, 2)
    tile_pin = "top-right"
    has_detail = False

    def create_tile(self, ctx: PluginContext) -> QWidget:
        return SystemStatsTile()

    def tile_clicked(self, ctx: PluginContext) -> None:
        monitor = find_monitor()
        if monitor and start_detached(monitor):
            ctx.request_close()

    def create_widget(self, ctx: PluginContext) -> QWidget:
        raise NotImplementedError  # has_detail is False: the app never asks for a page


PLUGIN = SystemPlugin()
