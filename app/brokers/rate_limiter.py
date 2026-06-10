import time


class RateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.0, interval_seconds)
        self._last_call_at = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call_at
        remaining = self.interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call_at = time.monotonic()
