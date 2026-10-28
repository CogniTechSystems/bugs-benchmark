"""Point-in-time statistics describing how a cache has been used."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CacheStats:
    """An immutable snapshot of the hit, miss, eviction and expiration counters of a cache, its live
    size and its capacity.
    """

    hits: int
    misses: int
    evictions: int
    expirations: int
    size: int
    capacity: int

    @property
    def lookups(self) -> int:
        """Return the total number of lookups, hits and misses combined."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Return the proportion of lookups that were hits, or zero if there were none."""
        return self.hits / self.lookups if self.lookups else 0.0

    @property
    def fill_ratio(self) -> float:
        """Return the proportion of the capacity currently occupied by live entries."""
        return self.size / self.capacity

    def __add__(self, other: "CacheStats") -> "CacheStats":
        """Return the field-by-field sum of two snapshots, describing a group of caches together."""
        return CacheStats(
            hits=self.hits + other.hits,
            misses=self.misses + other.misses,
            evictions=self.evictions + other.evictions,
            expirations=self.expirations + other.expirations,
            size=self.size + other.size,
            capacity=self.capacity + other.capacity,
        )

    def as_dict(self) -> dict[str, int | float]:
        """Return the counters and derived ratios as a plain dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "size": self.size,
            "capacity": self.capacity,
            "hit_rate": self.hit_rate,
            "fill_ratio": self.fill_ratio,
        }
