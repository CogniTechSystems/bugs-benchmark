import pytest
from cachekit import LRUCache, memoize


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_get_missing_key_returns_default():
    cache = LRUCache(2)
    assert cache.get("absent", "fallback") == "fallback"


def test_put_and_get():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.get("a") == 1


def test_updating_a_key_replaces_its_value():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("a", 2)
    assert cache.get("a") == 2
    assert len(cache) == 1


def test_get_marks_entry_as_recently_used():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    assert cache.keys() == ["b", "a"]


def test_eviction_removes_least_recently_used_entry():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.keys() == ["b", "c"]


def test_entry_is_available_before_expiry():
    clock = FakeClock()
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    clock.now = 9.5
    assert cache.get("a") == 1


def test_entry_expires_once_ttl_has_elapsed():
    clock = FakeClock()
    cache = LRUCache(2, ttl_seconds=10, clock=clock)
    cache.put("a", 1)
    clock.now = 10
    assert cache.get("a") is None
    assert len(cache) == 0


def test_delete():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.delete("a") is True
    assert cache.delete("a") is False


def test_hit_rate():
    cache = LRUCache(2)
    assert cache.hit_rate == 0.0
    cache.put("a", 1)
    cache.get("a")
    cache.get("b")
    assert cache.hit_rate == 0.5


@pytest.mark.parametrize("arguments", [{"capacity": 0}, {"capacity": 1, "ttl_seconds": 0}])
def test_invalid_configuration_is_rejected(arguments):
    with pytest.raises(ValueError):
        LRUCache(**arguments)


def test_memoize_caches_results():
    calls = []

    @memoize(capacity=4)
    def square(value):
        calls.append(value)
        return value * value

    assert square(3) == 9
    assert square(3) == 9
    assert calls == [3]
