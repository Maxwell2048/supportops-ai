"""Bounded process-local limiter for the single-process development API."""

from collections import deque
from hashlib import sha256
from threading import Lock
from time import monotonic

from supportops.errors import ApiError


class LoginLimiter:
    def __init__(self, *, email_limit=10, ip_limit=30, window_seconds=60, max_keys=4096, clock=monotonic):
        self.email_limit = email_limit
        self.ip_limit = ip_limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.clock = clock
        self._buckets: dict[str, deque] = {}
        self._lock = Lock()

    def check(self, email: str, ip: str):
        keys = [("email:" + sha256(email.encode()).hexdigest(), self.email_limit), ("ip:" + ip, self.ip_limit)]
        with self._lock:
            now = self.clock()
            cutoff = now - self.window_seconds
            # Bounded dictionary; expired identities do not accumulate forever.
            for key in list(self._buckets):
                bucket = self._buckets[key]
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._buckets[key]
            new_keys = sum(key not in self._buckets for key, _ in keys)
            full = len(self._buckets) + new_keys > self.max_keys
            if full or any(len(self._buckets.get(key, ())) >= limit for key, limit in keys):
                raise ApiError(429, "login_rate_limited", "Too many sign-in attempts; please try again later", {"Retry-After": str(self.window_seconds)})
            for key, _ in keys:
                self._buckets.setdefault(key, deque()).append(now)
