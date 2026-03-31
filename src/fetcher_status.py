from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import time


@dataclass
class FetcherStatusSnapshot:
    timestamp_epoch: float
    cooldowns: Dict[str, Dict[str, Any]]
    cache_entries: int

    def to_pretty_text(self) -> str:
        lines = []
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp_epoch))
        lines.append(f"Fetcher status @ {ts}")
        lines.append(f"- Cache entries: {self.cache_entries}")

        if not self.cooldowns:
            lines.append("- Cooldowns: none")
            return "\n".join(lines)

        lines.append("- Cooldowns:")
        # Sort soonest-expiring first
        items = sorted(self.cooldowns.items(), key=lambda kv: kv[1]["seconds_remaining"])
        for host, info in items:
            lines.append(
                f"  • {host}: {info['seconds_remaining']}s remaining "
                f"(fails={info.get('fails')}, last_status={info.get('last_status')})"
            )
        return "\n".join(lines)


def snapshot_fetcher(fetcher) -> FetcherStatusSnapshot:
    """
    Pull a safe snapshot of internal Fetcher state.
    Works with the upgraded src/fetcher.py you’re using.
    """
    now = time.time()

    cooldowns: Dict[str, Dict[str, Any]] = {}
    raw = getattr(fetcher, "_cooldowns", {}) or {}

    # _cooldowns: netloc -> (cooldown_until_epoch, consecutive_failures, last_status_code)
    for netloc, tup in raw.items():
        try:
            cooldown_until, fails, last_status = tup
            remaining = max(0, int(cooldown_until - now))
            if remaining > 0:
                cooldowns[netloc] = {
                    "cooldown_until": cooldown_until,
                    "seconds_remaining": remaining,
                    "fails": fails,
                    "last_status": last_status,
                }
        except Exception:
            # ignore malformed entries
            continue

    cache = getattr(fetcher, "_cache", {}) or {}
    cache_entries = len(cache)

    return FetcherStatusSnapshot(
        timestamp_epoch=now,
        cooldowns=cooldowns,
        cache_entries=cache_entries,
    )
