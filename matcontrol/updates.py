"""Update detection (dnf + flatpak) and output cleanup for the Update plugin. No root needed."""

import re
import subprocess
from dataclasses import dataclass

CHECK_TIMEOUT_S = 180
_PACKAGE_LINE = re.compile(r"^\S+\.\w+\s+\S+\s+\S+\s*$")  # "name.arch  version  repo"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass(frozen=True)
class UpdateStatus:
    count: int = 0
    error: str | None = None


def parse_dnf_check_update(output: str) -> int:
    """Count upgradable packages in `dnf check-update` output (stops at the obsoletes block)."""
    count = 0
    for line in output.splitlines():
        if line.lower().startswith("obsoleting"):
            break
        if _PACKAGE_LINE.match(line):
            count += 1
    return count


def parse_flatpak_updates(output: str) -> int:
    return sum(1 for line in output.splitlines() if line.strip())


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=CHECK_TIMEOUT_S)


def check() -> UpdateStatus:
    """Ask dnf (exit code 100 = updates) and flatpak how many updates are pending."""
    count = 0
    try:
        dnf = _run(["dnf", "check-update", "--refresh", "-q"])
        if dnf.returncode == 100:
            count += parse_dnf_check_update(dnf.stdout)
        elif dnf.returncode != 0:
            return UpdateStatus(error=(dnf.stderr.strip().splitlines() or ["dnf Fehler"])[-1])
    except FileNotFoundError:
        pass  # not a dnf system: flatpak may still report
    except subprocess.TimeoutExpired:
        return UpdateStatus(error="Zeitüberschreitung bei dnf")
    try:
        flatpak = _run(["flatpak", "remote-ls", "--updates", "--columns=application"])
        if flatpak.returncode == 0:
            count += parse_flatpak_updates(flatpak.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return UpdateStatus(count=count)


def clean_output(chunk: str) -> list[str]:
    """Split terminal output into display lines: drop ANSI codes, keep only the last
    state of lines that were redrawn with a carriage return (progress bars)."""
    lines = []
    for raw in _ANSI.sub("", chunk).split("\n"):
        text = raw.split("\r")[-1].rstrip()
        lines.append(text)
    return lines
