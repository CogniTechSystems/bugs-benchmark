"""Independent key spaces sharing a single cache."""

from collections.abc import Hashable
from typing import Any

from cachekit.lru import LRUCache


class NamespacedCache:
    """A view of a shared cache that stores each key paired with a namespace, so keys of different
    namespaces never collide.
    """

    def __init__(self, cache: LRUCache, namespace: str) -> None:
        """Create a view of ``cache`` for ``namespace``, raising ``ValueError`` if ``namespace`` is
        empty.
        """
        if not namespace:
            raise ValueError("namespace must not be empty")
        self._cache = cache
        self._namespace = namespace

    @property
    def namespace(self) -> str:
        """Return the name of this view's key space."""
        return self._namespace

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the live value for ``key`` in this namespace or ``default``, updating the shared
        recency order and counters.
        """
        return self._cache.get(self._qualify(key), default)

    def put(self, key: Hashable, value: Any) -> None:
        """Store ``value`` under ``key`` in this namespace as the most recently used entry of the
        shared cache.
        """
        self._cache.put(self._qualify(key), value)

    def delete(self, key: Hashable) -> bool:
        """Remove ``key`` from this namespace, returning whether a live entry was removed."""
        return self._cache.delete(self._qualify(key))

    def keys(self) -> list[Hashable]:
        """Return this namespace's live keys ordered from least to most recently used."""
        return [key[1] for key in self._cache if self._owns(key)]

    def clear(self) -> int:
        """Remove every entry in this namespace, leaving other namespaces untouched, and return how
        many live entries were removed.
        """
        return sum(self.delete(key) for key in self.keys())

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` holds a live entry in this namespace."""
        return (self._namespace, key) in self._cache

    def __len__(self) -> int:
        """Return the number of live entries in this namespace."""
        return len(self.keys())

    def _qualify(self, key: Hashable) -> tuple[str, Hashable]:
        """Return the key under which ``key`` is stored in the underlying cache."""
        return (self._namespace, key)

    def _owns(self, stored_key: Hashable) -> bool:
        """Return whether a key of the underlying cache belongs to this namespace."""
        return (
            isinstance(stored_key, tuple)
            and len(stored_key) == 2
            and stored_key[0] == self._namespace
        )
