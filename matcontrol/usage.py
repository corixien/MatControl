"""Claude weekly usage from Anthropic's usage endpoint (the same number claude.ai shows; it covers
claude.ai and Claude Code together). Uses the OAuth token Claude Code keeps in ~/.claude; the token
is only read and only sent to api.anthropic.com, never stored or logged. It is not refreshed here:
Claude Code does that."""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
URL = "https://api.anthropic.com/api/oauth/usage"
TIMEOUT_S = 15
WEEK_S = 7 * 86400


@dataclass(frozen=True)
class WeeklyUsage:
    percent: float  # 0..100
    resets_at: datetime | None


class UsageError(Exception):
    """Message is shown to the user (German)."""


def read_token(path: Path = CREDENTIALS, now: float | None = None) -> str:
    try:
        oauth = json.loads(path.read_text())["claudeAiOauth"]
        token = oauth["accessToken"]
    except (OSError, ValueError, KeyError, TypeError):
        raise UsageError("Nicht bei Claude Code angemeldet") from None
    expires_ms = oauth.get("expiresAt")
    if isinstance(expires_ms, (int, float)) and expires_ms / 1000 <= (time.time() if now is None else now):
        raise UsageError("Token abgelaufen, Claude Code starten")
    return token


def parse_usage(data: dict) -> WeeklyUsage:
    try:
        week = data["seven_day"]
        percent = float(week["utilization"])
    except (KeyError, TypeError, ValueError):
        raise UsageError("Unerwartete Antwort") from None
    resets_at = None
    raw = week.get("resets_at")
    if isinstance(raw, str):
        try:
            resets_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return WeeklyUsage(max(0.0, min(100.0, percent)), resets_at)


def fetch_weekly_usage() -> WeeklyUsage:
    """Blocking; call from a worker thread."""
    request = urllib.request.Request(
        URL,
        headers={"Authorization": f"Bearer {read_token()}", "anthropic-beta": "oauth-2025-04-20"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return parse_usage(json.load(response))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise UsageError("Token abgelaufen, Claude Code starten") from None
        raise UsageError("Limit-Abfrage gedrosselt" if exc.code == 429 else f"Fehler {exc.code}") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise UsageError("Keine Verbindung") from None


def pace_target(resets_at: datetime | None, now: datetime | None = None) -> float | None:
    """Percent of the weekly limit allowed by the end of today: 100/7 per started day of the week
    (the first day starts at the reset, so right after the reset it is already 14.3 %)."""
    if resets_at is None:
        return None
    elapsed = WEEK_S - (resets_at - (now or datetime.now(timezone.utc))).total_seconds()
    day = min(7, max(0, int(elapsed // 86400)) + 1)
    return 100.0 * day / 7
