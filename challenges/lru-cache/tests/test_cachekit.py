import json

import pytest
from cachekit import (
    CacheStats,
    EvictionLog,
    EvictionReason,
    LRUCache,
    ManualClock,
    NamespacedCache,
    dump_cache,
    load_cache,
    make_key,
    memoize,
)


def test_manual_clock_advances():
    clock = ManualClock(5.0)
    assert clock() == 5.0
    assert clock.advance(2.5) == 7.5
    assert clock() == 7.5


def test_manual_clock_rejects_moving_backwards():
    with pytest.raises(ValueError):
        ManualClock().advance(-1)


def test_eviction_log_counts_by_reason():
    log = EvictionLog()
    log("a", 1, EvictionReason.DELETED)
    log("b", 2, EvictionReason.EXPIRED)
    log("c", 3, EvictionReason.DELETED)
    assert log.count() == 3
    assert log.count(EvictionReason.DELETED) == 2
    assert log.keys(EvictionReason.DELETED) == ["a", "c"]
    assert log.keys() == ["a", "b", "c"]


def test_cache_stats_derived_values():
    stats = CacheStats(hits=3, misses=1, evictions=2, expirations=0, size=2, capacity=4)
    assert stats.lookups == 4
    assert stats.hit_rate == 0.75
    assert stats.fill_ratio == 0.5
    assert CacheStats(0, 0, 0, 0, 0, 1).hit_rate == 0.0


def test_cache_stats_can_be_combined():
    first = CacheStats(hits=1, misses=2, evictions=3, expirations=4, size=5, capacity=6)
    second = CacheStats(hits=10, misses=20, evictions=30, expirations=40, size=50, capacity=60)
    assert first + second == CacheStats(11, 22, 33, 44, 55, 66)
    assert first.as_dict()["hit_rate"] == pytest.approx(1 / 3)
    assert first.as_dict()["capacity"] == 6


def test_peek_leaves_recency_and_counters_unchanged():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.peek("a") == 1
    assert cache.peek("missing", "fallback") == "fallback"
    assert cache.keys() == ["a", "b"]
    assert (cache.hits, cache.misses) == (0, 0)


def test_membership_does_not_count_as_use():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    assert "a" in cache
    assert "c" not in cache
    assert cache.keys() == ["a", "b"]


def test_items_and_entries_follow_recency_order():
    clock = ManualClock()
    cache = LRUCache(3, clock=clock)
    cache.put("a", 1)
    clock.advance(2)
    cache.put("b", 2)
    clock.advance(1)
    assert cache.items() == [("a", 1), ("b", 2)]
    assert cache.entries() == [("a", 1, 3.0), ("b", 2, 1.0)]


def test_put_with_age_shortens_remaining_lifetime():
    cache = LRUCache(2, ttl_seconds=10, clock=ManualClock())
    cache.put("a", 1, age=4)
    assert cache.ttl_remaining("a") == 6


def test_put_rejects_negative_age():
    with pytest.raises(ValueError):
        LRUCache(2).put("a", 1, age=-1)


def test_ttl_remaining_without_live_entry_or_ttl():
    clock = ManualClock()
    assert LRUCache(2).ttl_remaining("a") is None
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    assert cache.ttl_remaining("a") is None
    cache.put("a", 1)
    clock.advance(11)
    assert cache.ttl_remaining("a") is None


def test_ttl_remaining_is_none_once_ttl_has_elapsed():
    clock = ManualClock()
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    clock.advance(10)
    assert cache.ttl_remaining("a") is None


def test_delete_of_expired_entry_reports_expiry():
    clock = ManualClock()
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    log = EvictionLog()
    cache.add_listener(log)
    cache.put("a", 1)
    clock.advance(11)
    assert cache.delete("a") is False
    assert log.keys(EvictionReason.EXPIRED) == ["a"]
    assert cache.expirations == 1


def test_delete_reports_removal_to_listeners():
    cache = LRUCache(2)
    log = EvictionLog()
    cache.add_listener(log)
    cache.put("a", 1)
    cache.delete("a")
    assert [(r.key, r.value, r.reason) for r in log.records] == [("a", 1, EvictionReason.DELETED)]


def test_clear_distinguishes_live_and_expired_entries():
    clock = ManualClock()
    cache = LRUCache(3, ttl_seconds=10, clock=clock)
    log = EvictionLog()
    cache.add_listener(log)
    cache.put("old", 1)
    clock.advance(8)
    cache.put("new", 2)
    clock.advance(5)
    cache.clear()
    assert len(cache) == 0
    assert log.keys(EvictionReason.EXPIRED) == ["old"]
    assert log.keys(EvictionReason.CLEARED) == ["new"]


def test_purge_expired_discards_only_expired_entries():
    clock = ManualClock()
    cache = LRUCache(3, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    cache.put("b", 2)
    clock.advance(6)
    cache.put("c", 3)
    clock.advance(6)
    assert cache.purge_expired() == 2
    assert cache.keys() == ["c"]
    assert cache.expirations == 2
    assert cache.purge_expired() == 0


def test_get_of_expired_entry_counts_expiration():
    clock = ManualClock()
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    clock.advance(20)
    assert cache.get("a") is None
    assert (cache.misses, cache.expirations) == (1, 1)


def test_capacity_evictions_are_counted():
    cache = LRUCache(2)
    log = EvictionLog()
    cache.add_listener(log)
    for key in "abcd":
        cache.put(key, key)
    assert len(cache) == 2
    assert cache.evictions == 2
    assert log.count(EvictionReason.CAPACITY) == 2


def test_capacity_eviction_reports_least_recently_used_key():
    cache = LRUCache(1)
    log = EvictionLog()
    cache.add_listener(log)
    cache.put("a", 1)
    cache.put("b", 2)
    assert log.keys(EvictionReason.CAPACITY) == ["a"]


def test_resize_shrinks_to_new_capacity():
    cache = LRUCache(4)
    for key in "abcd":
        cache.put(key, key)
    cache.resize(2)
    assert cache.capacity == 2
    assert len(cache) == 2
    assert cache.evictions == 2
    cache.resize(5)
    assert len(cache) == 2


def test_resize_evicts_least_recently_used_entries():
    cache = LRUCache(3)
    for key in "abc":
        cache.put(key, key)
    cache.resize(2)
    assert cache.keys() == ["b", "c"]


def test_resize_rejects_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(2).resize(0)


def test_removed_listener_is_not_called():
    cache = LRUCache(2)
    log = EvictionLog()
    cache.add_listener(log)
    cache.remove_listener(log)
    cache.put("a", 1)
    cache.delete("a")
    assert log.count() == 0
    with pytest.raises(ValueError):
        cache.remove_listener(log)


def test_stats_snapshot_and_reset():
    cache = LRUCache(4, ttl_seconds=30)
    assert cache.ttl_seconds == 30
    cache.put("a", 1)
    cache.get("a")
    cache.get("b")
    assert cache.stats() == CacheStats(
        hits=1, misses=1, evictions=0, expirations=0, size=1, capacity=4
    )
    cache.reset_stats()
    assert cache.stats().lookups == 0
    assert len(cache) == 1


def test_make_key_ignores_keyword_order():
    assert make_key((1, 2), {}) == (1, 2)
    assert make_key((1,), {"a": 1, "b": 2}) == make_key((1,), {"b": 2, "a": 1})
    assert make_key((1,), {"a": 2}) != make_key((1, "a", 2), {})


def test_memoize_supports_keyword_arguments():
    calls = []

    @memoize()
    def power(base, exponent=2):
        calls.append((base, exponent))
        return base**exponent

    assert power(2, exponent=3) == 8
    assert power(2, exponent=3) == 8
    assert power(2) == 4
    assert calls == [(2, 3), (2, 2)]


def test_memoize_preserves_metadata_and_reports_statistics():
    @memoize(capacity=8)
    def double(value):
        """Double a value."""
        return value * 2

    double(1)
    double(1)
    double(2)
    assert double.__name__ == "double"
    assert double.__doc__ == "Double a value."
    info = double.cache_info()
    assert (info.hits, info.misses, info.size, info.capacity) == (1, 2, 2, 8)


def test_memoize_cache_clear_forgets_results():
    calls = []

    @memoize()
    def identity(value):
        calls.append(value)
        return value

    identity(1)
    identity.cache_clear()
    identity(1)
    assert calls == [1, 1]
    assert identity.cache_info().lookups == 1


def test_memoize_recomputes_expired_results():
    clock = ManualClock()
    calls = []

    @memoize(ttl_seconds=10, clock=clock)
    def current(value):
        calls.append(value)
        return value

    current(1)
    clock.advance(5)
    current(1)
    clock.advance(10)
    current(1)
    assert calls == [1, 1]


def test_memoize_rejects_invalid_settings():
    with pytest.raises(ValueError):
        memoize(capacity=0)(lambda: None)


def test_namespaces_do_not_collide():
    shared = LRUCache(4)
    users = NamespacedCache(shared, "users")
    orders = NamespacedCache(shared, "orders")
    users.put(1, "alice")
    orders.put(1, "order-1")
    assert users.get(1) == "alice"
    assert orders.get(1) == "order-1"
    assert 1 in users
    assert 2 not in users
    assert users.namespace == "users"
    assert len(shared) == 2


def test_namespace_keys_and_clear():
    shared = LRUCache(5)
    shared.put("plain", 0)
    users = NamespacedCache(shared, "users")
    orders = NamespacedCache(shared, "orders")
    users.put("a", 1)
    users.put("b", 2)
    orders.put("a", 3)
    assert users.keys() == ["a", "b"]
    assert users.clear() == 2
    assert len(users) == 0
    assert orders.keys() == ["a"]
    assert shared.get("plain") == 0


def test_namespace_lookups_count_towards_shared_statistics():
    shared = LRUCache(4)
    users = NamespacedCache(shared, "users")
    users.put("a", 1)
    users.get("a")
    users.get("missing")
    assert users.delete("a") is True
    assert users.delete("a") is False
    assert (shared.hits, shared.misses) == (1, 1)


def test_namespace_get_marks_entry_as_recently_used():
    users = NamespacedCache(LRUCache(4), "users")
    users.put("a", 1)
    users.put("b", 2)
    users.get("a")
    assert users.keys() == ["b", "a"]


def test_namespace_requires_a_name():
    with pytest.raises(ValueError):
        NamespacedCache(LRUCache(1), "")


def test_snapshot_round_trip_preserves_order_and_age():
    source_clock = ManualClock()
    source = LRUCache(4, ttl_seconds=10, clock=source_clock)
    source.put("a", [1, 2])
    source_clock.advance(3)
    source.put("b", {"x": 1})
    source_clock.advance(2)
    snapshot = dump_cache(source)

    target = LRUCache(4, ttl_seconds=10, clock=ManualClock(100))
    assert load_cache(snapshot, target) == 2
    assert target.items() == [("a", [1, 2]), ("b", {"x": 1})]
    assert target.ttl_remaining("a") == 5
    assert target.ttl_remaining("b") == 8


def test_load_skips_entries_that_have_outlived_the_ttl():
    snapshot = json.dumps(
        {
            "version": 1,
            "entries": [
                {"key": "stale", "value": 1, "age": 10},
                {"key": "fresh", "value": 2, "age": 9},
            ],
        }
    )
    cache = LRUCache(4, ttl_seconds=10, clock=ManualClock())
    assert load_cache(snapshot, cache) == 1
    assert cache.keys() == ["fresh"]


def test_dump_requires_string_keys():
    cache = LRUCache(2)
    cache.put(1, "one")
    with pytest.raises(TypeError):
        dump_cache(cache)


@pytest.mark.parametrize(
    "snapshot",
    [
        "not json",
        json.dumps({"version": 2, "entries": []}),
        json.dumps({"version": 1}),
        json.dumps({"version": 1, "entries": [{"key": 1, "value": 1, "age": 0}]}),
        json.dumps({"version": 1, "entries": [{"key": "a", "age": 0}]}),
        json.dumps({"version": 1, "entries": [{"key": "a", "value": 1, "age": -1}]}),
    ],
)
def test_load_rejects_malformed_snapshots(snapshot):
    with pytest.raises(ValueError):
        load_cache(snapshot, LRUCache(2))


def test_iteration_yields_live_keys_in_recency_order():
    clock = ManualClock()
    cache = LRUCache(3, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    clock.advance(6)
    cache.put("b", 2)
    cache.put("c", 3)
    clock.advance(6)
    assert list(cache) == ["b", "c"]
