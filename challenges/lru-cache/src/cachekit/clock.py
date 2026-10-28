"""Time sources used to measure how long cache entries have been stored."""

import time
from collections.abc import Callable

Clock = Callable[[], float]
"""A zero-argument callable returning the current time in seconds as a float."""


def system_clock() -> float:
    """Return the current monotonic time in seconds, a reading that never goes backwards."""
    return time.monotonic()


class ManualClock:
    """A callable clock that only moves when advanced, for deterministic control of entry ages."""

    def __init__(self, start: float = 0.0) -> None:
        """Create a clock that reads ``start`` until it is advanced."""
        self._now = start

    def __call__(self) -> float:
        """Return the current reading of the clock in seconds."""
        return self._now

    def advance(self, seconds: float) -> float:
        """Move the clock forward by ``seconds`` and return the new reading, raising ``ValueError``
        if ``seconds`` is negative.
        """
        if seconds < 0:
            raise ValueError("a clock cannot move backwards")
        self._now += seconds
        return self._now
