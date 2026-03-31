import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from tenacity import Retrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.robots import RobotsCache

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Raised for HTTP/network failures that should be handled by retry/cooldown logic."""
    pass


@dataclass
class Fetcher:
    timeout_seconds: int
    max_retries: int
    user_agents: list

    # Etiquette + stability
    respect_robots_txt: bool = True
    cache_ttl_seconds: int = 900  # cache successful GET responses for 15 min

    # Smarter blocking behavior (host cooldown)
    cooldown_base_seconds: int = 15 * 60       # 15 minutes
    cooldown_max_seconds: int = 6 * 60 * 60    # 6 hours
    max_recent_failures: int = 3               # after N failures, enter cooldown

    def __post_init__(self):
        self._robots = RobotsCache(ttl_seconds=3600)

        # URL cache: url -> (expires_at_epoch, response)
        self._cache: Dict[str, Tuple[float, requests.Response]] = {}

        # Host cooldown state:
        # netloc -> (cooldown_until_epoch, consecutive_failures, last_status_code)
        self._cooldowns: Dict[str, Tuple[float, int, Optional[int]]] = {}

    def _choose_ua(self) -> str:
        return random.choice(self.user_agents) if self.user_agents else "Mozilla/5.0"

    def _headers(self, ua: str) -> Dict[str, str]:
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

    def _netloc(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _robots_allowed(self, ua: str, url: str) -> bool:
        if not self.respect_robots_txt:
            return True
        return self._robots.can_fetch(ua, url)

    def _cooldown_remaining(self, netloc: str) -> Optional[int]:
        entry = self._cooldowns.get(netloc)
        if not entry:
            return None
        cooldown_until, _fails, _status = entry
        now = time.time()
        if cooldown_until > now:
            return int(cooldown_until - now)
        return None

    def _set_cooldown(self, netloc: str, status_code: Optional[int], retry_after_seconds: Optional[int] = None):
        """
        Put host into cooldown. Duration grows with consecutive failures.
        If Retry-After is provided, honor it (take max).
        """
        now = time.time()
        current = self._cooldowns.get(netloc)

        if current:
            _until, fails, _prev = current
            fails += 1
        else:
            fails = 1

        # Exponential-ish: base * 2^(fails-1), capped
        dur = min(self.cooldown_base_seconds * (2 ** (fails - 1)), self.cooldown_max_seconds)

        if retry_after_seconds is not None:
            dur = max(dur, int(retry_after_seconds))

        cooldown_until = now + dur
        self._cooldowns[netloc] = (cooldown_until, fails, status_code)

        logger.warning(
            "Host cooldown set: %s | status=%s | fails=%s | duration=%ss",
            netloc, status_code, fails, dur
        )

    def _record_success(self, netloc: str):
        # Reset failures on success
        if netloc in self._cooldowns:
            self._cooldowns.pop(netloc, None)

    def _record_failure(self, netloc: str, status_code: Optional[int]):
        """
        Record a failure; if failures reach threshold, enter cooldown.
        If already in cooldown, keep it.
        """
        now = time.time()
        current = self._cooldowns.get(netloc)
        if current:
            cooldown_until, fails, _ = current
            if cooldown_until > now:
                # Already cooling down; keep it, just update last status
                self._cooldowns[netloc] = (cooldown_until, fails, status_code)
                return
            fails += 1
        else:
            fails = 1

        # Store a "not in cooldown yet" entry with until=now
        self._cooldowns[netloc] = (now, fails, status_code)

        if fails >= self.max_recent_failures:
            self._set_cooldown(netloc, status_code)

    def get(self, url: str, *, allow_redirects: bool = True) -> requests.Response:
        """
        GET with:
        - per-URL caching (TTL)
        - optional robots.txt respect
        - retry + exponential backoff
        - 429 Retry-After support
        - per-host cooldown after repeated failures (403/429/5xx/network)
        """
        now = time.time()

        # URL cache
        cached = self._cache.get(url)
        if cached and cached[0] > now:
            return cached[1]

        netloc = self._netloc(url)

        # Host cooldown gate
        remaining = self._cooldown_remaining(netloc)
        if remaining is not None:
            raise FetchError(f"Host in cooldown for {remaining}s: {netloc}")

        # Choose UA once for the whole retry chain (reduces weirdness)
        ua = self._choose_ua()

        # Robots.txt etiquette
        if not self._robots_allowed(ua, url):
            # Treat robots block as a short cooldown to avoid repeated hits
            self._set_cooldown(netloc, status_code=None, retry_after_seconds=300)
            raise FetchError(f"Blocked by robots.txt: {url}")

        retryer = Retrying(
            stop=stop_after_attempt(max(1, int(self.max_retries))),
            wait=wait_exponential(multiplier=1, min=1, max=12),
            retry=retry_if_exception_type((requests.RequestException, FetchError)),
            reraise=True,
        )

        for attempt in retryer:
            with attempt:
                try:
                    resp = requests.get(
                        url,
                        headers=self._headers(ua),
                        timeout=self.timeout_seconds,
                        allow_redirects=allow_redirects,
                    )

                    # Rate limited
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("Retry-After")
                        retry_after_seconds = None
                        if retry_after and str(retry_after).strip().isdigit():
                            retry_after_seconds = int(str(retry_after).strip())

                        # Cooldown + retry
                        self._set_cooldown(netloc, status_code=429, retry_after_seconds=retry_after_seconds)
                        raise FetchError(f"HTTP 429 for {url}")

                    # Blocked/Forbidden: long cooldown (don’t hammer)
                    if resp.status_code in (401, 403):
                        self._set_cooldown(netloc, status_code=resp.status_code)
                        raise FetchError(f"HTTP {resp.status_code} for {url}")

                    # Server errors: record + retry; may cooldown after repeated
                    if 500 <= resp.status_code <= 599:
                        self._record_failure(netloc, resp.status_code)
                        raise FetchError(f"HTTP {resp.status_code} for {url}")

                    # Other client errors
                    if resp.status_code >= 400:
                        self._record_failure(netloc, resp.status_code)
                        raise FetchError(f"HTTP {resp.status_code} for {url}")

                    # Success
                    self._record_success(netloc)
                    self._cache[url] = (time.time() + int(self.cache_ttl_seconds), resp)
                    return resp

                except requests.RequestException as e:
                    # Network error: record + retry; may cooldown after repeated
                    logger.warning("Network error for %s: %s", url, e)
                    self._record_failure(netloc, None)
                    raise

        # Should never reach here because reraise=True
        raise FetchError(f"Failed to fetch after retries: {url}")
