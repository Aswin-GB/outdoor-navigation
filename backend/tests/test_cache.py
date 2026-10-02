from cache import redis as cache


def test_memory_cache_returns_value_before_ttl(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(cache, 'get_redis_client', lambda: None)
    monkeypatch.setattr(cache.time, 'monotonic', lambda: now[0])
    cache.clear_cache()

    cache.set_cached_item('test-route-cache', {'route_id': 'route-1'}, ttl=5)

    assert cache.get_cached_item('test-route-cache') == {'route_id': 'route-1'}

    now[0] += 5
    assert cache.get_cached_item('test-route-cache') is None
