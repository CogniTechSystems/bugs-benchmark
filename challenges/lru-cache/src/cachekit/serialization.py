"""Saving a cache's contents as JSON and restoring them later."""

import json
from typing import Any

from cachekit.lru import LRUCache

FORMAT_VERSION = 1
"""The version number written to, and required in, every snapshot."""


def dump_cache(cache: LRUCache) -> str:
    """Return a JSON snapshot of live entries with their ages, least recently used first, raising
    ``TypeError`` for non-string keys or unserialisable values.
    """
    records = []
    for key, value, age in cache.entries():
        if not isinstance(key, str):
            raise TypeError(f"only string keys can be saved, got {type(key).__name__}")
        records.append({"key": key, "value": value, "age": age})
    return json.dumps({"version": FORMAT_VERSION, "entries": records})


def load_cache(snapshot: str, cache: LRUCache) -> int:
    """Store snapshot entries into ``cache`` in saved order with saved ages, skipping any whose age
    has reached the time to live, and return the count.
    """
    records = _parse(snapshot)
    ttl = cache.ttl_seconds
    stored = 0
    for record in records:
        if ttl is not None and record["age"] >= ttl:
            continue
        cache.put(record["key"], record["value"], age=record["age"])
        stored += 1
    return stored


def _parse(snapshot: str) -> list[dict[str, Any]]:
    """Return the validated snapshot records, raising ``ValueError`` for invalid JSON, an
    unsupported version, or a record lacking a string key, value or non-negative age.
    """
    try:
        document = json.loads(snapshot)
    except json.JSONDecodeError as error:
        raise ValueError("snapshot is not valid JSON") from error
    if not isinstance(document, dict) or document.get("version") != FORMAT_VERSION:
        raise ValueError("unsupported snapshot version")
    records = document.get("entries")
    if not isinstance(records, list):
        raise ValueError("snapshot has no entry list")
    for record in records:
        if not (
            isinstance(record, dict)
            and isinstance(record.get("key"), str)
            and "value" in record
            and isinstance(record.get("age"), int | float)
            and record["age"] >= 0
        ):
            raise ValueError(f"malformed snapshot entry: {record!r}")
    return records
