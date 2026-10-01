"""
Traffic service - main entry point for traffic management.
Coordinates presence, scoring, weights, and rerouting.
"""
import json
import logging
import time
from typing import Optional

from django.conf import settings
from traffic.presence import PresenceManager
from traffic.scoring import TrafficScorer
from traffic.weights import WeightCalculator
from traffic.analyzer import RouteImpactAnalyzer
from routing_engine.manager import get_graph_manager
from cache.redis import get_redis_client
from analytics.services import AnalyticsService

logger = logging.getLogger('traffic')


class TrafficService:
    """Main service for traffic management."""

    def __init__(self):
        self.presence = PresenceManager()
        self.scorer = TrafficScorer()
        self.weights = WeightCalculator()
        self.analyzer = RouteImpactAnalyzer()
        self.graph_manager = get_graph_manager()
        self.analytics = AnalyticsService()
        self._traffic_version = 0

    def get_traffic_version(self) -> int:
        """Get current traffic version."""
        try:
            client = get_redis_client()
            if client:
                version = client.get('traffic_version')
                if version:
                    return int(version)
        except Exception:
            pass
        return self._traffic_version

    def _increment_traffic_version(self):
        """Increment the traffic version."""
        self._traffic_version += 1
        try:
            client = get_redis_client()
            if client:
                client.set('traffic_version', self._traffic_version)
        except Exception:
            pass

    def process_telemetry(self, session_id: str, lat: float, lng: float, timestamp: str = None) -> dict:
        """
        Process a telemetry update from a user.
        This is the main entry point for GPS data.
        """
        start_time = time.perf_counter()

        # Map match to edge
        graph = self.graph_manager.get_graph()
        if not graph or not graph.spatial_index:
            return {'success': False, 'error': 'Graph not available'}

        from routing_engine.matcher import MapMatcher
        matcher = MapMatcher(graph.spatial_index)
        match = matcher.match(lat, lng)

        if not match:
            return {'success': False, 'error': 'No matching road found'}

        edge_id = match['edge_id']

        # Update presence
        presence_result = self.presence.update_presence(session_id, edge_id, lat, lng)
        if not presence_result['success']:
            return presence_result

        active_count = presence_result['active_users']

        # Update edge weight
        edge = graph.edges.get(edge_id)
        if edge:
            old_time = edge.get('current_time_sec', edge.get('base_time_sec', 0))
            new_time = self.weights.update_edge_weight(edge, active_count)

            # Update in-memory graph
            self.graph_manager.update_edge_weight(edge_id, new_time)

            # Check if traffic level changed
            old_level = edge.get('traffic_level', 'LOW')
            new_level = self.scorer.classify_by_count(active_count)

            if old_level != new_level:
                self._increment_traffic_version()
                self.analytics.record_traffic_state_change()
                logger.info(f"Traffic level changed on {edge_id}: {old_level} -> {new_level}")

        # Record telemetry
        self.analytics.record_telemetry()

        processing_time = (time.perf_counter() - start_time) * 1000

        return {
            'success': True,
            'edge_id': edge_id,
            'active_users': active_count,
            'traffic_level': new_level if edge else 'LOW',
            'match_confidence': match.get('confidence', 'LOW'),
            'match_distance_m': match.get('distance_m', 0),
            'processing_time_ms': round(processing_time, 2),
            'traffic_version': self.get_traffic_version(),
        }

    def get_traffic_state(self, edge_id: str) -> dict:
        """Get traffic state for a specific edge."""
        graph = self.graph_manager.get_graph()
        if not graph:
            return {'success': False, 'error': 'Graph not available'}

        edge = graph.edges.get(edge_id)
        if not edge:
            return {'success': False, 'error': 'Edge not found'}

        active_count = self.presence.get_edge_count(edge_id)
        state = self.weights.get_edge_state(edge, active_count)

        return {
            'success': True,
            'data': state,
        }

    def get_all_traffic(self) -> dict:
        """Get traffic state for all edges."""
        graph = self.graph_manager.get_graph()
        if not graph:
            return {'success': False, 'error': 'Graph not available'}

        active_edges = self.presence.get_all_active_edges()
        result = {}

        for edge_id, count in active_edges.items():
            edge = graph.edges.get(edge_id)
            if edge:
                state = self.weights.get_edge_state(edge, count)
                result[edge_id] = state

        return {
            'success': True,
            'data': {
                'edges': result,
                'traffic_version': self.get_traffic_version(),
                'active_edge_count': len(result),
            }
        }

    def stop_sharing(self, session_id: str) -> dict:
        """Stop sharing location for a session."""
        result = self.presence.remove_presence(session_id)
        if result['success']:
            self._increment_traffic_version()
        return result

    def add_simulated_users(self, edge_id: str, count: int) -> dict:
        """Add simulated users to an edge (for demo mode)."""
        graph = self.graph_manager.get_graph()
        if not graph or edge_id not in graph.edges:
            return {'success': False, 'error': 'Edge not found'}

        # Add simulated presence
        for i in range(count):
            sim_session = f"sim_{edge_id}_{int(time.time())}_{i}"
            self.presence.update_presence(sim_session, edge_id, 0, 0)

        # Update weight
        edge = graph.edges[edge_id]
        active_count = self.presence.get_edge_count(edge_id)
        self.weights.update_edge_weight(edge, active_count)
        self.graph_manager.update_edge_weight(edge_id, edge['current_time_sec'])
        self._increment_traffic_version()

        return {
            'success': True,
            'edge_id': edge_id,
            'active_users': active_count,
            'simulated': True,
        }

    def remove_simulated_users(self, edge_id: str, count: int = None) -> dict:
        """Remove simulated users from an edge."""
        # In a real implementation, we'd track simulated sessions
        # For now, reset to 0
        client = get_redis_client()
        if client:
            key = f"active_users:{edge_id}"
            if count is None:
                client.delete(key)
            else:
                members = client.smembers(key)
                for i, member in enumerate(members):
                    if i >= count:
                        break
                    client.srem(key, member)

        graph = self.graph_manager.get_graph()
        if graph and edge_id in graph.edges:
            edge = graph.edges[edge_id]
            active_count = self.presence.get_edge_count(edge_id)
            self.weights.update_edge_weight(edge, active_count)
            self.graph_manager.update_edge_weight(edge_id, edge['current_time_sec'])

        self._increment_traffic_version()

        return {'success': True, 'edge_id': edge_id, 'simulated': True}

    def reset_simulation(self) -> dict:
        """Reset all simulated traffic."""
        client = get_redis_client()
        if client:
            keys = client.keys("active_users:*")
            for key in keys:
                client.delete(key)

        # Reset all edge weights
        graph = self.graph_manager.get_graph()
        if graph:
            for edge_id, edge in graph.edges.items():
                edge['current_time_sec'] = edge.get('base_time_sec', 0)
                edge['traffic_level'] = 'LOW'
                edge['traffic_factor'] = 1.0

        self._increment_traffic_version()

        return {'success': True, 'simulated': True}
