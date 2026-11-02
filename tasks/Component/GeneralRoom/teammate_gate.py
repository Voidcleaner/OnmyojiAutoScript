"""Require a continuously present teammate before the host starts a room."""
import random
import time


class TeammateGate:
    def __init__(self, delay=None):
        self.delay = random.uniform(3, 5) if delay is None else delay
        self.joined_at = None

    def ready(self, present, now=None):
        now = time.monotonic() if now is None else now
        if not present:
            self.joined_at = None
            return False
        if self.joined_at is None:
            self.joined_at = now
        return now - self.joined_at >= self.delay
