from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import threading
import time


class RobotsCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cache = {}  # netloc -> (expires_at, parser)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        with self._lock:
            entry = self._cache.get(netloc)
            now = time.time()
            if entry and entry[0] > now:
                rp = entry[1]
                return rp.can_fetch(user_agent, url)

        rp = RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{netloc}/robots.txt")
        try:
            rp.read()
        except Exception:
            # If robots.txt can't be read, default allow (common practice),
            # but you can flip this to False if you want strict.
            return True

        with self._lock:
            self._cache[netloc] = (time.time() + self.ttl, rp)

        return rp.can_fetch(user_agent, url)
