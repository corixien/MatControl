import sys

import pytest
from PySide6.QtWidgets import QApplication

from conftest import wait
from matcontrol import sysstats
from matcontrol.config import Config
from matcontrol.plugin_base import Plugin, PluginContext
from matcontrol.plugins import system
from matcontrol.window import COLUMNS, MainWindow, place_tiles

STAT_1 = "cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 1 1 1 1 1 1 1 1 1 1\n"
STAT_2 = "cpu  200 0 200 750 150 0 0 0 0 0\n"
MEMINFO = "MemTotal:       16000000 kB\nMemFree:         1000000 kB\nMemAvailable:    4000000 kB\n"
NET_1 = (
    "Inter-|   Receive                                                |  Transmit\n"
    " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
    "    lo: 999 1 0 0 0 0 0 0 999 1 0 0 0 0 0 0\n"
    "  wlp3s0: 1000 10 0 0 0 0 0 0 500 5 0 0 0 0 0 0\n"
    "  enp1s0: 2000 10 0 0 0 0 0 0 100 5 0 0 0 0 0 0\n"
    " veth123: 5555 1 0 0 0 0 0 0 5555 1 0 0 0 0 0 0\n"
)
NET_2 = NET_1.replace("wlp3s0: 1000", "wlp3s0: 3000").replace(" 500 5", " 1500 5")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_parse_cpu_times_and_percent():
    first, second = sysstats.parse_cpu_times(STAT_1), sysstats.parse_cpu_times(STAT_2)
    assert first == (800, 1000) and second == (900, 1300)
    assert sysstats.cpu_percent(first, second) == pytest.approx(100 * (1 - 100 / 300))
    assert sysstats.cpu_percent(first, first) == 0.0


def test_parse_meminfo_uses_available():
    assert sysstats.parse_meminfo(MEMINFO) == (12000000, 16000000)


def test_parse_net_dev_skips_loopback_and_virtual_interfaces():
    assert sysstats.parse_net_dev(NET_1) == (3000, 600)


@pytest.mark.parametrize(
    ("value", "text"),
    [(0, "0 B/s"), (812, "812 B/s"), (1500, "1.5 KB/s"), (2_500_000, "2.5 MB/s"), (3e9, "3.0 GB/s")],
)
def test_format_rate(value, text):
    assert sysstats.format_rate(value) == text


def test_sampler_reports_usage_since_last_call():
    files = {"/proc/stat": STAT_1, "/proc/net/dev": NET_1, "/proc/meminfo": MEMINFO}
    clock = iter([0.0, 2.0])
    sampler = sysstats.Sampler(read=lambda path: files[path], clock=lambda: next(clock))
    files["/proc/stat"], files["/proc/net/dev"] = STAT_2, NET_2
    stats = sampler.sample()
    assert stats.cpu_percent == pytest.approx(100 * (1 - 100 / 300))
    assert stats.rx_bytes_per_s == pytest.approx(1000.0) and stats.tx_bytes_per_s == pytest.approx(500.0)
    assert stats.ram_percent == pytest.approx(75.0) and stats.ram_total_gb == pytest.approx(16000000 / 1024 / 1024)


class Normal(Plugin):
    def __init__(self, plugin_id):
        self.id, self.name = plugin_id, plugin_id

    def create_widget(self, ctx):
        raise NotImplementedError


def test_stats_tile_takes_the_top_right_corner_and_others_flow_around_it():
    big = system.SystemPlugin()
    others = [Normal("a"), Normal("b"), Normal("c"), Normal("d")]
    placed = place_tiles([*others, big])  # order in the list must not matter for the pinned tile
    assert placed[big.id] == (0, COLUMNS - 2)
    assert placed["a"] == (0, 0) and placed["b"] == (1, 0)
    assert placed["c"] == (2, 0) and placed["d"] == (2, 2)  # below the big tile the row is free again


def test_pinned_tile_never_overlaps_others():
    plugins = [Normal(str(i)) for i in range(6)] + [system.SystemPlugin()]
    placed = place_tiles(plugins)
    cells = set()
    for plugin in plugins:
        width, height = plugin.tile_cells
        row, column = placed[plugin.id]
        mine = {(r, c) for r in range(row, row + height) for c in range(column, column + width)}
        assert not mine & cells
        cells |= mine


def test_click_launches_the_monitor_and_closes_the_popup(qapp, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(system, "find_monitor", lambda: "/usr/bin/plasma-systemmonitor")
    monkeypatch.setattr(system, "start_detached", lambda program: launched.append(program) or True)
    ctx = PluginContext(Config(tmp_path / "c.json"), "system")
    closed = []
    ctx.close_requested.connect(lambda: closed.append(1))
    system.SystemPlugin().tile_clicked(ctx)
    assert launched == ["/usr/bin/plasma-systemmonitor"] and closed == [1]


def test_click_without_a_monitor_app_keeps_the_popup_open(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(system, "find_monitor", lambda: None)
    ctx = PluginContext(Config(tmp_path / "c.json"), "system")
    closed = []
    ctx.close_requested.connect(lambda: closed.append(1))
    system.SystemPlugin().tile_clicked(ctx)
    assert closed == []


def test_window_has_no_detail_page_for_the_stats_tile_and_click_launches(qapp, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(system, "find_monitor", lambda: "/bin/monitor")
    monkeypatch.setattr(system, "start_detached", lambda program: launched.append(program) or True)
    window = MainWindow(Config(tmp_path / "c.json"), [system.PLUGIN], [], popup=False)
    assert "system" not in window.pages and window.stack.count() == 1
    window.tiles["system"].opened.emit()
    assert launched == ["/bin/monitor"] and window.stack.currentIndex() == 0


def test_stats_tile_updates_while_visible(qapp):
    files = {"/proc/stat": STAT_1, "/proc/net/dev": NET_1, "/proc/meminfo": MEMINFO}
    sampler = sysstats.Sampler(read=lambda path: files[path])
    tile = system.SystemStatsTile(sampler)
    tile.show()
    files["/proc/stat"], files["/proc/net/dev"] = STAT_2, NET_2
    wait(500)
    assert tile.cpu.value.text().endswith("%") and tile.cpu.value.text() != "–"
    assert tile.ram.value.text().startswith("11.4 / 15.3")
    assert "↓" in tile.net.value.text() and "↑" in tile.net.value.text()
    tile.hide()
    assert not tile.timer.isActive()
