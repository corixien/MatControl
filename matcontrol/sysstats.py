"""CPU, RAM and network numbers from /proc for the System tile. Pure parsing plus a small sampler."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

VIRTUAL_PREFIXES = ("lo", "veth", "docker", "br-", "virbr", "vnet", "tun", "tap")


@dataclass(frozen=True)
class Stats:
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    rx_bytes_per_s: float
    tx_bytes_per_s: float


def parse_cpu_times(stat_text: str) -> tuple[int, int]:
    """(idle, total) jiffies from the aggregate "cpu" line of /proc/stat."""
    fields = [int(x) for x in stat_text.splitlines()[0].split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    return idle, sum(fields[:8])  # guest time is already inside user/nice


def cpu_percent(previous: tuple[int, int], current: tuple[int, int]) -> float:
    total = current[1] - previous[1]
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (1 - (current[0] - previous[0]) / total)))


def parse_meminfo(text: str) -> tuple[int, int]:
    """(used_kib, total_kib); "used" is total minus available, like most system monitors."""
    values = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            values[key] = int(rest.split()[0])
    total = values.get("MemTotal", 0)
    return max(0, total - values.get("MemAvailable", total)), total


def parse_net_dev(text: str) -> tuple[int, int]:
    """Total (rx_bytes, tx_bytes) over all real interfaces."""
    rx = tx = 0
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        if not rest or name.strip().startswith(VIRTUAL_PREFIXES):
            continue
        fields = rest.split()
        rx += int(fields[0])
        tx += int(fields[8])
    return rx, tx


def format_rate(bytes_per_s: float) -> str:
    value = max(0.0, bytes_per_s)
    for unit in ("B/s", "KB/s", "MB/s"):
        if value < 1000:
            return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} GB/s"


def _read(path: str) -> str:
    return Path(path).read_text()


class Sampler:
    """Keeps the previous readings so each sample() reports usage since the last call."""

    def __init__(self, read: Callable[[str], str] = _read, clock: Callable[[], float] | None = None):
        import time

        self._read = read
        self._clock = clock or time.monotonic
        self.reset()

    def reset(self) -> None:
        """Take a new baseline; the next sample() reports CPU and network since now."""
        self._cpu = parse_cpu_times(self._read("/proc/stat"))
        self._net = parse_net_dev(self._read("/proc/net/dev"))
        self._at = self._clock()

    def sample(self) -> Stats:
        cpu = parse_cpu_times(self._read("/proc/stat"))
        net = parse_net_dev(self._read("/proc/net/dev"))
        now = self._clock()
        elapsed = max(now - self._at, 1e-3)
        used, total = parse_meminfo(self._read("/proc/meminfo"))
        stats = Stats(
            cpu_percent=cpu_percent(self._cpu, cpu),
            ram_used_gb=used / 1024 / 1024,
            ram_total_gb=total / 1024 / 1024,
            ram_percent=100.0 * used / total if total else 0.0,
            rx_bytes_per_s=max(0, net[0] - self._net[0]) / elapsed,
            tx_bytes_per_s=max(0, net[1] - self._net[1]) / elapsed,
        )
        self._cpu, self._net, self._at = cpu, net, now
        return stats
