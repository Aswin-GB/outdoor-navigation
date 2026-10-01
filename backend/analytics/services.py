"""
Analytics service for tracking system metrics.
"""
import time
import logging
from typing import Optional
from cache.redis import get_redis_client

logger = logging.getLogger('analytics')


class AnalyticsService:
    """Tracks and reports system performance metrics."""

    def __init__(self):
        self._local_fallback = {
            'route_requests': 0,
            'astar_runs': 0,
            'astar_latency_total': 0.0,
            'astar_latency_count': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'reroutes': 0,
            'telemetry_updates': 0,
            'traffic_state_changes': 0,
            'websocket_connections': 0,
            'map_edits': 0,
        }

    def _get_redis(self):
        try:
            return get_redis_client()
        except Exception:
            return None

    def _incr(self, key: str, amount: int = 1):
        """Increment a counter in Redis or local fallback."""
        client = self._get_redis()
        if client:
            try:
                client.hincrby('metrics', key, amount)
                return
            except Exception:
                pass
        self._local_fallback[key] = self._local_fallback.get(key, 0) + amount

    def _get(self, key: str) -> int:
        """Get a counter value."""
        client = self._get_redis()
        if client:
            try:
                val = client.hget('metrics', key)
                if val:
                    return int(val)
            except Exception:
                pass
        return self._local_fallback.get(key, 0)

    def record_route_request(self, latency_ms: float):
        """Record a route request."""
        self._incr('route_requests')
        logger.info(f"Route request: {latency_ms:.2f}ms")

    def record_astar_run(self, latency_ms: float):
        """Record an A* execution."""
        self._incr('astar_runs')
        self._incr('astar_latency_total', int(latency_ms * 1000))  # Store as microseconds
        self._incr('astar_latency_count')
        logger.info(f"A* run: {latency_ms:.2f}ms")

    def record_cache_hit(self):
        """Record a cache hit."""
        self._incr('cache_hits')

    def record_cache_miss(self):
        """Record a cache miss."""
        self._incr('cache_misses')

    def record_reroute(self):
        """Record a reroute."""
        self._incr('reroutes')

    def record_telemetry(self):
        """Record a telemetry update."""
        self._incr('telemetry_updates')

    def record_traffic_state_change(self):
        """Record a traffic state change."""
        self._incr('traffic_state_changes')

    def record_websocket_connect(self):
        """Record a WebSocket connection."""
        self._incr('websocket_connections')

    def record_map_edit(self):
        """Record a map edit."""
        self._incr('map_edits')

    def get_metrics(self) -> dict:
        """Get all metrics."""
        route_requests = self._get('route_requests')
        astar_runs = self._get('astar_runs')
        astar_latency_total = self._get('astar_latency_total')
        astar_latency_count = self._get('astar_latency_count')
        cache_hits = self._get('cache_hits')
        cache_misses = self._get('cache_misses')

        avg_astar_latency = 0.0
        if astar_latency_count > 0:
            avg_astar_latency = (astar_latency_total / astar_latency_count) / 1000  # Convert back to ms

        total_cache = cache_hits + cache_misses
        cache_hit_rate = 0.0
        if total_cache > 0:
            cache_hit_rate = (cache_hits / total_cache) * 100

        # Get active users from traffic service
        active_users = 0
        try:
            from traffic.service import TrafficService
            ts = TrafficService()
            all_traffic = ts.get_all_traffic()
            if all_traffic.get('success'):
                active_users = sum(
                    e.get('active_users', 0)
                    for e in all_traffic['data'].get('edges', {}).values()
                )
        except Exception:
            pass

        # Get versions
        from routing_engine.manager import get_graph_manager
        gm = get_graph_manager()
        graph_version = gm.get_graph_version()
        map_version = gm.get_map_version()

        from traffic.service import TrafficService
        traffic_version = TrafficService().get_traffic_version()

        return {
            'route_requests': route_requests,
            'astar_runs': astar_runs,
            'astar_avg_latency_ms': round(avg_astar_latency, 3),
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_hit_rate': round(cache_hit_rate, 2),
            'reroutes': self._get('reroutes'),
            'telemetry_updates': self._get('telemetry_updates'),
            'traffic_state_changes': self._get('traffic_state_changes'),
            'active_users': active_users,
            'websocket_connections': self._get('websocket_connections'),
            'map_edits': self._get('map_edits'),
            'graph_version': graph_version,
            'map_version': map_version,
            'traffic_version': traffic_version,
        }
