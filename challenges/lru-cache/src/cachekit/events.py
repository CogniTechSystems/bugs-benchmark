"""Notifications sent when entries leave a cache."""

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EvictionReason(StrEnum):
    """Why an entry was removed from a cache."""

    CAPACITY = "capacity"
    EXPIRED = "expired"
    DELETED = "deleted"
    CLEARED = "cleared"


EvictionListener = Callable[[Hashable, Any, EvictionReason], None]
"""A callable invoked with the key, value and reason of each entry removed from a cache."""


@dataclass(frozen=True)
class Eviction:
    """A record of a single entry leaving a cache."""

    key: Hashable
    value: Any
    reason: EvictionReason


class EvictionLog:
    """An eviction listener that records every removal it is told about, in removal order."""

    def __init__(self) -> None:
        """Create an empty log."""
        self.records: list[Eviction] = []

    def __call__(self, key: Hashable, value: Any, reason: EvictionReason) -> None:
        """Append a record describing the removal of ``key``."""
        self.records.append(Eviction(key, value, reason))

    def count(self, reason: EvictionReason | None = None) -> int:
        """Return how many removals were recorded, optionally only those for ``reason``."""
        if reason is None:
            return len(self.records)
        return sum(1 for record in self.records if record.reason is reason)

    def keys(self, reason: EvictionReason | None = None) -> list[Hashable]:
        """Return the removed keys in removal order, optionally only those for ``reason``."""
        return [record.key for record in self.records if reason is None or record.reason is reason]
