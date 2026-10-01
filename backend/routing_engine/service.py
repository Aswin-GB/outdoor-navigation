"""
Routing service - orchestrates A* pathfinding with caching and traffic weights.
"""
import hashlib
import json
import logging
import time
import uuid
from typing import Optional

from django.conf import settings
from routing_engine.astar import astar, haversine_m
from routing_engine.manager import get_graph_manager
from cache.redis import get_redis_client
from analytics.services import AnalyticsService

logger = logging.getLogger('routing')


class RoutingService:
    """Service for computing fastest routes using A* with dynamic traffic weights."""

    def __init__(self):
        self.graph_manager = get_graph_manager()
        self.analytics = AnalyticsService()
        self._redis_available = None

    def _get_cache_key(self, source_node: str, dest_node: str, map_version: int, traffic_version: int) -> str:
        """Generate cache key for a route."""
        return f"route:{source_node}:{dest_node}:M{map_version}:T{traffic_version}"

    def _is_redis_available(self) -> bool:
        """Check if Redis is available (cached result)."""
        if self._redis_available is not None:
            return self._redis_available
        try:
            client = get_redis_client()
            self._redis_available = client is not None
        except Exception:
            self._redis_available = False
        return self._redis_available

    def _get_cached_route(self, cache_key: str) -> Optional[dict]:
        """Try to get a cached route from Redis."""
        if not self._is_redis_available():
            return None
        try:
            client = get_redis_client()
            if client:
                cached = client.get(cache_key)
                if cached:
                    route = json.loads(cached)
                    route['cache'] = 'HIT'
                    return route
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")
            self._redis_available = False
        return None

    def _cache_route(self, cache_key: str, route: dict, ttl: int = 300):
        """Cache a route in Redis."""
        if not self._is_redis_available():
            return
        try:
            client = get_redis_client()
            if client:
                client.setex(cache_key, ttl, json.dumps(route))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
            self._redis_available = False

    def find_nearest_node(self, lat: float, lng: float, max_distance_m: float = 500.0) -> Optional[str]:
        """Find the nearest graph node to a coordinate."""
        graph = self.graph_manager.get_graph()
        if not graph or not graph.nodes:
            return None

        best_node = None
        best_dist = float('inf')

        for node_id, node in graph.nodes.items():
            dist = haversine_m(lat, lng, node['lat'], node['lng'])
            if dist < best_dist:
                best_dist = dist
                best_node = node_id

        if best_node and best_dist <= max_distance_m:
            return best_node
        return None

    def compute_route(
        self,
        source_lat: float,
        source_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = 'walking',
    ) -> dict:
        """
        Compute the fastest route between two points.

        Returns route dict with path, distance, duration, etc.
        """
        start_time = time.perf_counter()

        graph = self.graph_manager.get_graph()
        if not graph:
            return {
                'success': False,
                'error': {
                    'code': 'GRAPH_NOT_LOADED',
                    'message': 'Routing graph is not loaded.',
                }
            }

        # Find nearest nodes
        source_node = self.find_nearest_node(source_lat, source_lng)
        dest_node = self.find_nearest_node(dest_lat, dest_lng)

        if not source_node:
            return {
                'success': False,
                'error': {
                    'code': 'SOURCE_UNREACHABLE',
                    'message': 'No graph node found near source location.',
                }
            }

        if not dest_node:
            return {
                'success': False,
                'error': {
                    'code': 'DESTINATION_UNREACHABLE',
                    'message': 'No graph node found near destination.',
                }
            }

        # Get versions
        map_version = self.graph_manager.get_map_version()
        traffic_version = 0
        try:
            from traffic.service import TrafficService
            traffic_version = TrafficService().get_traffic_version()
        except Exception:
            pass

        # Check cache
        cache_key = self._get_cache_key(source_node, dest_node, map_version, traffic_version)
        cached = self._get_cached_route(cache_key)
        if cached:
            self.analytics.record_cache_hit()
            cached['source_node'] = source_node
            cached['dest_node'] = dest_node
            return {
                'success': True,
                'data': cached,
            }

        self.analytics.record_cache_miss()

        # Build graph dict for A*
        graph_dict = {
            'nodes': graph.nodes,
            'adjacency': graph.adjacency,
        }

        # Get current time function for dynamic weights
        current_time_func = graph.get_edge_weight_func()

        # Run A*
        result = astar(graph_dict, source_node, dest_node, current_time_func)

        if result is None:
            return {
                'success': False,
                'error': {
                    'code': 'ROUTE_NOT_FOUND',
                    'message': 'No walkable route exists between source and destination.',
                }
            }

        # Record metrics
        self.analytics.record_astar_run(result['latency_ms'])

        # Build response
        route_data = {
            'route_id': result['route_id'],
            'path': result['coordinates'],
            'node_path': result['path'],
            'distance_m': result['distance_m'],
            'duration_sec': result['duration_sec'],
            'algorithm': 'A*',
            'cache': 'MISS',
            'map_version': map_version,
            'traffic_version': traffic_version,
            'source_node': source_node,
            'dest_node': dest_node,
            'astar_latency_ms': result['latency_ms'],
            'nodes_executed': result['nodes_executed'],
        }

        # Cache the route
        self._cache_route(cache_key, route_data)

        # Record route latency
        total_latency = (time.perf_counter() - start_time) * 1000
        self.analytics.record_route_request(total_latency)

        return {
            'success': True,
            'data': route_data,
        }

    def reroute(
        self,
        route_id: str,
        current_lat: float,
        current_lng: float,
        dest_lat: float,
        dest_lng: float,
        reason: str = 'traffic_change',
    ) -> dict:
        """
        Compute a new route from current position to destination.
        Used for mid-journey rerouting.
        """
        result = self.compute_route(current_lat, current_lng, dest_lat, dest_lng)

        if result['success']:
            result['data']['rerouted'] = True
            result['data']['reason'] = reason
            self.analytics.record_reroute()
        else:
            result['data'] = {
                'rerouted': False,
                'reason': reason,
            }

        return result
