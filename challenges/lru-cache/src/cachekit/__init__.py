"""In-process caching: an LRU cache with expiry, namespaces, persistence and memoisation."""

from cachekit.clock import Clock, ManualClock, system_clock
from cachekit.events import Eviction, EvictionListener, EvictionLog, EvictionReason
from cachekit.lru import LRUCache
from cachekit.memoize import MemoizedFunction, make_key, memoize
from cachekit.namespace import NamespacedCache
from cachekit.serialization import dump_cache, load_cache
from cachekit.stats import CacheStats

__all__ = [
    "CacheStats",
    "Clock",
    "Eviction",
    "EvictionListener",
    "EvictionLog",
    "EvictionReason",
    "LRUCache",
    "ManualClock",
    "MemoizedFunction",
    "NamespacedCache",
    "dump_cache",
    "load_cache",
    "make_key",
    "memoize",
    "system_clock",
]
