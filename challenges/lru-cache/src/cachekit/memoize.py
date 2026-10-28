"""Function memoisation backed by an LRU cache."""

import functools
from collections.abc import Callable, Hashable
from typing import Any, Generic, TypeVar

from cachekit.clock import Clock, system_clock
from cachekit.lru import LRUCache
from cachekit.stats import CacheStats

ResultT = TypeVar("ResultT")

_NOT_CACHED = object()
_KEYWORD_MARKER = object()


def make_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Hashable:
    """Return a hashable key for a call, the positional tuple alone or followed by a marker and
    keyword items sorted by name.
    """
    if not kwargs:
        return args
    return (*args, _KEYWORD_MARKER, *sorted(kwargs.items()))


class MemoizedFunction(Generic[ResultT]):
    """A callable that keeps the results of the function it wraps in a least-recently-used cache
    keyed by hashable arguments.
    """

    def __init__(self, function: Callable[..., ResultT], cache: LRUCache) -> None:
        """Wrap ``function``, storing its results in ``cache``."""
        self._function = function
        self.cache = cache
        functools.update_wrapper(self, function)

    def __call__(self, *args: Any, **kwargs: Any) -> ResultT:
        """Return the cached result for these arguments, calling the function on a miss."""
        key = make_key(args, kwargs)
        result = self.cache.get(key, _NOT_CACHED)
        if result is _NOT_CACHED:
            result = self._function(*args, **kwargs)
            self.cache.put(key, result)
        return result

    def cache_info(self) -> CacheStats:
        """Return a snapshot of the underlying cache's statistics."""
        return self.cache.stats()

    def cache_clear(self) -> None:
        """Forget every cached result and reset the statistics."""
        self.cache.clear()
        self.cache.reset_stats()


def memoize(
    capacity: int = 128, ttl_seconds: float | None = None, clock: Clock = system_clock
) -> Callable[[Callable[..., ResultT]], MemoizedFunction[ResultT]]:
    """Return a decorator giving each function its own cache of at most ``capacity`` results, each
    recomputed once cached for ``ttl_seconds``.
    """

    def decorator(function: Callable[..., ResultT]) -> MemoizedFunction[ResultT]:
        """Wrap ``function`` with a fresh cache built from the decorator settings."""
        return MemoizedFunction(function, LRUCache(capacity, ttl_seconds, clock))

    return decorator
