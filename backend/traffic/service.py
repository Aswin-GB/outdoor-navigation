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
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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

    def _broadcast_traffic_update(self, edge_id: str, active_count: int, traffic_level: str, current_time: float):
        """Broadcast traffic update to all active navigation groups."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                # Get all active navigation sessions
                from navigation.models import NavigationSession
                active_navs = NavigationSession.objects.filter(status='active')
                for nav in active_navs:
                    group_name = f'navigation_{nav.id}'
                    async_to_sync(channel_layer.group_send)(
                        group_name,
                        {
                            'type': 'traffic_update',
                            'edge_id': edge_id,
                            'active_user_count': active_count,
                            'traffic_level': traffic_level,
                            'current_time_sec': current_time,
                            'traffic_version': self.get_traffic_version(),
                        }
                    )
        except Exception as e:
            logger.warning(f"Failed to broadcast traffic update: {e}")

    def _broadcast_route_changed(self, navigation_id: str, route_id: str, reason: str, eta_sec: float, path: list):
        """Broadcast route change to a specific navigation group."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                group_name = f'navigation_{navigation_id}'
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'route_changed',
                        'route_id': route_id,
                        'reason': reason,
                        'eta_sec': eta_sec,
                        'path': path,
                        'traffic_version': self.get_traffic_version(),
                        'map_version': self.graph_manager.get_map_version(),
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast route change: {e}")

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
            # Read old state BEFORE mutation
            old_level = edge.get('traffic_level', 'LOW')

            # Calculate and apply new state
            new_time = self.weights.update_edge_weight(edge, active_count)
            new_level = self.scorer.classify_by_count(active_count)

            # Update in-memory graph
            self.graph_manager.update_edge_weight(edge_id, new_time)

            # Update metadata in the edge object
            edge['traffic_level'] = new_level

            # Only increment version on meaningful state change
            if old_level != new_level:
                self._increment_traffic_version()
                self.analytics.record_traffic_state_change()
                logger.info(f"Traffic level changed on {edge_id}: {old_level} -> {new_level}")

        # Reroute Analysis
        self._analyze_and_trigger_reroutes(edge_id, active_count)

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

    def _get_navigation_route_context(self, nav):
        """Attempt to resolve route edges and ETA context for an active navigation session."""
        try:
            current_position = nav.current_position or {}
            current_lat = current_position.get('lat')
            current_lng = current_position.get('lng')
            destination = nav.destination or {}
            destination_lat = destination.get('lat')
            destination_lng = destination.get('lng')
            if current_lat is None or current_lng is None or destination_lat is None or destination_lng is None:
                return {'route_edges': [], 'old_eta': 0.0, 'new_eta': 0.0, 'current_lat': current_lat, 'current_lng': current_lng, 'destination_lat': destination_lat, 'destination_lng': destination_lng}

            graph = self.graph_manager.get_graph()
            if not graph:
                return {'route_edges': [], 'old_eta': 0.0, 'new_eta': 0.0, 'current_lat': current_lat, 'current_lng': current_lng, 'destination_lat': destination_lat, 'destination_lng': destination_lng}

            from routing_engine.service import RoutingService
            route_result = RoutingService().compute_route(current_lat, current_lng, destination_lat, destination_lng)
            if not route_result.get('success'):
                return {'route_edges': [], 'old_eta': 0.0, 'new_eta': 0.0, 'current_lat': current_lat, 'current_lng': current_lng, 'destination_lat': destination_lat, 'destination_lng': destination_lng}

            route_data = route_result['data']
            route_edges = []
            node_path = route_data.get('node_path', [])
            for idx in range(len(node_path) - 1):
                from_node = node_path[idx]
                to_node = node_path[idx + 1]
                for neighbor, edge_id, _ in graph.adjacency.get(from_node, []):
                    if neighbor == to_node:
                        route_edges.append(edge_id)
                        break

            old_eta = float(route_data.get('duration_sec', 0.0) or 0.0)
            new_eta = old_eta
            return {
                'route_edges': route_edges,
                'old_eta': old_eta,
                'new_eta': new_eta,
                'current_lat': current_lat,
                'current_lng': current_lng,
                'destination_lat': destination_lat,
                'destination_lng': destination_lng,
            }
        except Exception as exc:
            logger.warning(f"Could not resolve route context for navigation {nav.id}: {exc}")
            return {'route_edges': [], 'old_eta': 0.0, 'new_eta': 0.0, 'current_lat': None, 'current_lng': None, 'destination_lat': None, 'destination_lng': None}

    def _analyze_and_trigger_reroutes(self, edge_id: str, active_count: int):
        """Analyze active navigation sessions to see if they need rerouting."""
        try:
            from navigation.models import NavigationSession
            from routing_engine.service import RoutingService

            active_navs = NavigationSession.objects.filter(status='active')
            graph = self.graph_manager.get_graph()
            if not graph:
                return

            for nav in active_navs:
                context = self._get_navigation_route_context(nav)
                route_edges = context['route_edges']
                old_eta = float(context['old_eta'] or 0.0)
                new_eta = old_eta

                current_edge = nav.current_edge
                if current_edge and current_edge == edge_id:
                    current_status = graph.edges.get(current_edge, {})
                    current_time = float(current_status.get('current_time_sec', current_status.get('base_time_sec', 0.0)) or 0.0)
                    if current_time > 0:
                        new_eta = old_eta + max(0.0, current_time - current_status.get('base_time_sec', current_time))

                decision = self.analyzer.should_reroute(str(nav.id), old_eta, new_eta, edge_id, route_edges)
                if not decision.get('should_reroute'):
                    continue

                current_lat = context.get('current_lat')
                current_lng = context.get('current_lng')
                dest_lat = context.get('destination_lat')
                dest_lng = context.get('destination_lng')
                if current_lat is None or current_lng is None or dest_lat is None or dest_lng is None:
                    continue

                reroute_result = RoutingService().reroute(
                    str(nav.id),
                    float(current_lat),
                    float(current_lng),
                    float(dest_lat),
                    float(dest_lng),
                    reason=f"traffic_change:{edge_id}"
                )
                if not reroute_result.get('success'):
                    continue

                route_data = reroute_result.get('data', {})
                path = route_data.get('path', [])
                eta = float(route_data.get('duration_sec', old_eta) or old_eta)
                self._broadcast_route_changed(str(nav.id), route_data.get('route_id', nav.route_id), decision.get('reason', 'traffic_change'), eta, path)
                logger.info(f"Triggered reroute for navigation {nav.id} because edge {edge_id} changed traffic: {decision.get('reason')}")

        except Exception as e:
            logger.warning(f"Reroute analysis failed: {e}")

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
                # Include geometry for frontend rendering
                state['geometry'] = self._get_edge_geometry(graph, edge_id)
                result[edge_id] = state

        return {
            'success': True,
            'data': {
                'edges': result,
                'traffic_version': self.get_traffic_version(),
                'active_edge_count': len(result),
            }
        }

    def _get_edge_geometry(self, graph, edge_id: str) -> dict:
        """Get the geometry for an edge from the graph."""
        edge = graph.edges.get(edge_id)
        if not edge:
            return None

        from_node = graph.nodes.get(edge.get('from'))
        to_node = graph.nodes.get(edge.get('to'))

        if not from_node or not to_node:
            return None

        return {
            'type': 'LineString',
            'coordinates': [
                [from_node['lng'], from_node['lat']],
                [to_node['lng'], to_node['lat']]
            ]
        }

    def stop_sharing(self, session_id: str) -> dict:
        """Stop sharing location for a session."""
        result = self.presence.remove_presence(session_id)
        if result['success']:
            self._increment_traffic_version()
        return result

    def _get_simulated_sessions(self, edge_id: str) -> list:
        """Get all simulated session IDs for an edge."""
        client = get_redis_client()
        if not client:
            return []
        try:
            members = client.smembers(f"active_users:{edge_id}")
            sim_sessions = []
            for m in members:
                sid = m.decode() if isinstance(m, bytes) else m
                if sid.startswith('sim_'):
                    sim_sessions.append(sid)
            return sim_sessions
        except Exception:
            return []

    def add_simulated_users(self, edge_id: str, count: int) -> dict:
        """Add simulated users to an edge (for demo mode)."""
        graph = self.graph_manager.get_graph()
        if not graph or edge_id not in graph.edges:
            return {'success': False, 'error': 'Edge not found'}

        # Add simulated presence with tracked session IDs
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
        """Remove only simulated users from an edge, preserving real users."""
        client = get_redis_client()
        sim_sessions = self._get_simulated_sessions(edge_id)

        if client and sim_sessions:
            if count is None:
                # Remove all simulated sessions
                for sid in sim_sessions:
                    client.srem(f"active_users:{edge_id}", sid)
            else:
                # Remove only up to count simulated sessions
                for sid in sim_sessions[:count]:
                    client.srem(f"active_users:{edge_id}", sid)

        graph = self.graph_manager.get_graph()
        if graph and edge_id in graph.edges:
            edge = graph.edges[edge_id]
            active_count = self.presence.get_edge_count(edge_id)
            self.weights.update_edge_weight(edge, active_count)
            self.graph_manager.update_edge_weight(edge_id, edge['current_time_sec'])

        self._increment_traffic_version()

        return {'success': True, 'edge_id': edge_id, 'simulated': True}

    def reset_simulation(self) -> dict:
        """Reset all simulated traffic without affecting real users."""
        client = get_redis_client()
        if client:
            keys = client.keys("active_users:*")
            for key in keys:
                edge_id = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
                sim_sessions = self._get_simulated_sessions(edge_id)
                for sid in sim_sessions:
                    client.srem(key, sid)

        graph = self.graph_manager.get_graph()
        if graph:
            for edge_id, edge in graph.edges.items():
                edge['current_time_sec'] = edge.get('base_time_sec', 0)
                edge['traffic_level'] = 'LOW'
                edge['traffic_factor'] = 1.0
                self.graph_manager.update_edge_weight(edge_id, 'LOW')

        self._increment_traffic_version()

        return {'success': True, 'simulated': True}
