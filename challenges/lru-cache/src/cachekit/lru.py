"""A least-recently-used cache with optional entry expiry."""

from collections import OrderedDict
from collections.abc import Hashable, Iterator
from typing import Any

from cachekit.clock import Clock, system_clock
from cachekit.events import EvictionListener, EvictionReason
from cachekit.stats import CacheStats

_MISSING = object()


class LRUCache:
    """A bounded mapping that evicts its least recently used entry when full and can expire entries
    after a fixed time to live.
    """

    def __init__(
        self,
        capacity: int,
        ttl_seconds: float | None = None,
        clock: Clock = system_clock,
    ) -> None:
        """Create an empty cache of at most ``capacity`` entries living ``ttl_seconds``, raising
        ``ValueError`` for a capacity below one or a non-positive lifetime.
        """
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self._listeners: list[EvictionListener] = []
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    @property
    def capacity(self) -> int:
        """Return the maximum number of entries the cache holds."""
        return self._capacity

    @property
    def ttl_seconds(self) -> float | None:
        """Return the lifetime of each entry in seconds, or ``None`` when entries never expire."""
        return self._ttl

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value under ``key`` or ``default``, counting hits and misses and marking
        a hit most recently used.
        """
        entry = self._entries.get(key, _MISSING)
        if entry is _MISSING:
            self.misses += 1
            return default
        value, stored_at = entry
        if self._is_expired(stored_at):
            self._discard(key, EvictionReason.EXPIRED)
            self.misses += 1
            return default
        self.hits += 1
        return value

    def peek(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value under ``key`` or ``default`` without changing the recency order or
        the counters.
        """
        entry = self._entries.get(key, _MISSING)
        if entry is _MISSING:
            return default
        value, stored_at = entry
        return default if self._is_expired(stored_at) else value

    def put(self, key: Hashable, value: Any, *, age: float = 0.0) -> None:
        """Store ``value`` under ``key`` as most recently used, aged by ``age`` seconds, then evict
        to fit, rejecting a negative ``age``.
        """
        if age < 0:
            raise ValueError("age cannot be negative")
        if key in self._entries:
            self._entries.move_to_end(key)
        self._entries[key] = (value, self._clock() - age)
        self._enforce_capacity()

    def delete(self, key: Hashable) -> bool:
        """Remove the entry under ``key`` and return whether it was live, discarding an expired
        entry as expired.
        """
        entry = self._entries.get(key, _MISSING)
        if entry is _MISSING:
            return False
        _, stored_at = entry
        if self._is_expired(stored_at):
            self._discard(key, EvictionReason.EXPIRED)
            return False
        self._discard(key, EvictionReason.DELETED)
        return True

    def clear(self) -> None:
        """Remove every entry, reporting live ones as cleared and the rest as expired."""
        for key, (_, stored_at) in list(self._entries.items()):
            expired = self._is_expired(stored_at)
            self._discard(key, EvictionReason.EXPIRED if expired else EvictionReason.CLEARED)

    def purge_expired(self) -> int:
        """Discard every expired entry, reporting each as expired, and return how many were
        discarded.
        """
        expired = [
            key for key, (_, stored_at) in self._entries.items() if self._is_expired(stored_at)
        ]
        for key in expired:
            self._discard(key, EvictionReason.EXPIRED)
        return len(expired)

    def resize(self, capacity: int) -> None:
        """Change the capacity, evicting least recently used entries until the cache fits, and
        reject a capacity below one.
        """
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._enforce_capacity()

    def keys(self) -> list[Hashable]:
        """Return the live keys ordered from least to most recently used."""
        return [
            key for key, (_, stored_at) in self._entries.items() if not self._is_expired(stored_at)
        ]

    def items(self) -> list[tuple[Hashable, Any]]:
        """Return the live ``(key, value)`` pairs ordered from least to most recently used."""
        return [
            (key, value)
            for key, (value, stored_at) in self._entries.items()
            if not self._is_expired(stored_at)
        ]

    def entries(self) -> list[tuple[Hashable, Any, float]]:
        """Return live ``(key, value, age)`` triples from least to most recently used, where age is
        seconds since storing.
        """
        now = self._clock()
        return [
            (key, value, now - stored_at)
            for key, (value, stored_at) in self._entries.items()
            if not self._is_expired(stored_at)
        ]

    def ttl_remaining(self, key: Hashable) -> float | None:
        """Return the positive seconds left before the entry under ``key`` expires, or ``None`` if
        it is not live or never expires.
        """
        entry = self._entries.get(key, _MISSING)
        if entry is _MISSING or self._ttl is None:
            return None
        _, stored_at = entry
        if self._is_expired(stored_at):
            return None
        return stored_at + self._ttl - self._clock()

    def add_listener(self, listener: EvictionListener) -> None:
        """Register ``listener`` to be called with the key, value and reason after each entry is
        removed.
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: EvictionListener) -> None:
        """Stop notifying ``listener``, raising ``ValueError`` if it was never registered."""
        self._listeners.remove(listener)

    def stats(self) -> CacheStats:
        """Return a snapshot of the hit, miss, eviction and expiration counters with the live size
        and capacity.
        """
        return CacheStats(
            hits=self.hits,
            misses=self.misses,
            evictions=self.evictions,
            expirations=self.expirations,
            size=len(self),
            capacity=self._capacity,
        )

    def reset_stats(self) -> None:
        """Set the hit, miss, eviction and expiration counters back to zero."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    @property
    def hit_rate(self) -> float:
        """Return the proportion of counted lookups that were hits, or zero before any lookup."""
        lookups = self.hits + self.misses
        return self.hits / lookups if lookups else 0.0

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` holds a live entry, without changing its recency."""
        entry = self._entries.get(key, _MISSING)
        return entry is not _MISSING and not self._is_expired(entry[1])

    def __iter__(self) -> Iterator[Hashable]:
        """Iterate over a copy of the live keys, from least to most recently used."""
        return iter(self.keys())

    def __len__(self) -> int:
        """Return the number of live entries."""
        return len(self.keys())

    def _enforce_capacity(self) -> None:
        """Evict least recently used entries, reporting each as a capacity eviction, until at most
        ``capacity`` entries remain.
        """
        while len(self._entries) > self._capacity:
            evicted_key, (evicted_value, _) = self._entries.popitem(last=True)
            self.evictions += 1
            self._notify(evicted_key, evicted_value, EvictionReason.CAPACITY)

    def _discard(self, key: Hashable, reason: EvictionReason) -> None:
        """Remove the entry under ``key``, counting an expiration when ``reason`` is expiry, and
        notify listeners.
        """
        value, _ = self._entries.pop(key)
        if reason is EvictionReason.EXPIRED:
            self.expirations += 1
        self._notify(key, value, reason)

    def _notify(self, key: Hashable, value: Any, reason: EvictionReason) -> None:
        """Call every registered listener with the removed key, its value and the reason, in
        registration order.
        """
        for listener in list(self._listeners):
            listener(key, value, reason)

    def _is_expired(self, stored_at: float) -> bool:
        """Return whether an entry stored at ``stored_at`` has expired, which happens once
        ``ttl_seconds`` have elapsed since storing.
        """
        return self._ttl is not None and self._clock() - stored_at > self._ttl
