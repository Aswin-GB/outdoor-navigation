"""
Traffic service - main traffic processing pipeline.

Handles:
- Redis/Valkey presence tracking
- crowd-based traffic scoring
- dynamic edge weights
- manual traffic simulation
- simulated-user traffic
- active-route impact analysis
- automatic rerouting
- WebSocket traffic/route updates
"""

import logging
import time
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from analytics.services import AnalyticsService
from cache.redis import get_redis_client
from navigation.models import NavigationSession
from routing_engine.manager import get_graph_manager
from routing_engine.matcher import MapMatcher
from traffic.analyzer import RouteImpactAnalyzer
from traffic.presence import PresenceManager
from traffic.scoring import TrafficScorer
from traffic.weights import WeightCalculator

logger = logging.getLogger("traffic")


class TrafficService:
    """Main service for traffic processing and simulation."""

    SPEEDS_KMH = {
        "LOW": 40.0,
        "MODERATE": 30.0,
        "MEDIUM": 30.0,
        "HIGH": 18.0,
        "SEVERE": 7.0,
        "CLOSED": 0.0,
    }

    def __init__(self):
        self.presence = PresenceManager()
        self.scorer = TrafficScorer()
        self.weights = WeightCalculator()
        self.analyzer = RouteImpactAnalyzer()
        self.graph_manager = get_graph_manager()
        self.analytics = AnalyticsService()
        self._traffic_version = 0

    # ------------------------------------------------------------------
    # TRAFFIC VERSION
    # ------------------------------------------------------------------

    def get_traffic_version(self) -> int:
        """Return the current global traffic version."""
        try:
            client = get_redis_client()
            if client:
                value = client.get("traffic_version")
                if value is not None:
                    return int(value)
        except Exception as exc:
            logger.warning("Unable to read traffic version: %s", exc)

        return self._traffic_version

    def _increment_traffic_version(self) -> int:
        """Increment the global traffic version."""
        self._traffic_version += 1

        try:
            client = get_redis_client()
            if client:
                value = self._traffic_version
                client.set("traffic_version", value)
                return value
        except Exception as exc:
            logger.warning("Unable to persist traffic version: %s", exc)

        return self._traffic_version

    # ------------------------------------------------------------------
    # GRAPH HELPERS
    # ------------------------------------------------------------------

    def _set_exact_edge_weight(
        self,
        edge_id: str,
        current_time_sec: float,
        traffic_level: Optional[str] = None,
        traffic_factor: Optional[float] = None,
    ) -> bool:
        """Set the exact dynamic time on an edge and its adjacency entry."""
        graph = self.graph_manager.get_graph()
        if not graph or edge_id not in graph.edges:
            return False

        edge = graph.edges[edge_id]
        edge["current_time_sec"] = float(current_time_sec)

        if traffic_level is not None:
            edge["traffic_level"] = traffic_level

        if traffic_factor is not None:
            edge["traffic_factor"] = float(traffic_factor)

        from_node = edge.get("from")
        adjacency = graph.adjacency.get(from_node, [])

        for index, (neighbor, eid, _old_weight) in enumerate(adjacency):
            if eid == edge_id:
                adjacency[index] = (
                    neighbor,
                    eid,
                    float(current_time_sec),
                )
                break

        return True

    def _calculate_level_time(
        self,
        edge: dict,
        traffic_level: str,
    ) -> tuple[float, float]:
        """Return (travel_time_seconds, traffic_factor) for a level."""
        level = str(traffic_level).strip().upper()
        speed_kmh = self.SPEEDS_KMH[level]
        distance_m = float(edge.get("distance_m", 0.0) or 0.0)
        base_time = float(edge.get("base_time_sec", 0.0) or 0.0)

        if speed_kmh <= 0:
            current_time = float("inf")
        else:
            current_time = distance_m / (speed_kmh * 1000.0 / 3600.0)

        factor = 1.0 if base_time <= 0 else current_time / base_time
        return current_time, factor

    def _apply_manual_level(
        self,
        edge_id: str,
        traffic_level: str,
    ) -> dict:
        """Apply a manually simulated traffic level to an edge."""
        graph = self.graph_manager.get_graph()
        if not graph:
            return {
                "success": False,
                "error": "Graph not available",
            }

        edge = graph.edges.get(edge_id)
        if not edge:
            return {
                "success": False,
                "error": "Edge not found",
            }

        level = str(traffic_level).strip().upper()
        if level not in self.SPEEDS_KMH:
            return {
                "success": False,
                "error": f"Invalid traffic level: {traffic_level}",
            }

        old_level = edge.get("traffic_level", "LOW")
        old_time = float(
            edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )
            or 0.0
        )

        new_time, factor = self._calculate_level_time(edge, level)

        changed = (
            old_level != level
            or (
                old_time != float("inf")
                and new_time != float("inf")
                and abs(old_time - new_time) > 0.01
            )
            or (old_time == float("inf")) != (new_time == float("inf"))
        )

        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=level,
            traffic_factor=factor,
        )

        return {
            "success": True,
            "changed": changed,
            "edge_id": edge_id,
            "previous_traffic_level": old_level,
            "traffic_level": level,
            "previous_time_sec": old_time,
            "current_time_sec": new_time,
            "traffic_factor": factor,
            "active_users": self.presence.get_edge_count(edge_id),
        }

    # ------------------------------------------------------------------
    # ROUTE / ETA HELPERS
    # ------------------------------------------------------------------

    def _nodes_to_edges(self, graph, node_path: list) -> list:
        """Convert a node path to edge IDs."""
        edge_path = []

        for index in range(max(0, len(node_path) - 1)):
            from_node = node_path[index]
            to_node = node_path[index + 1]

            selected_edge = None
            for neighbor, edge_id, _weight in graph.adjacency.get(from_node, []):
                if neighbor == to_node:
                    selected_edge = edge_id
                    break

            if selected_edge is None:
                return []

            edge_path.append(selected_edge)

        return edge_path

    def _route_edges_from_result(self, graph, route_data: dict) -> list:
        """Resolve route edge IDs from a RoutingService response."""
        edge_path = route_data.get("edge_path")
        if isinstance(edge_path, list) and edge_path:
            return edge_path

        return self._nodes_to_edges(
            graph,
            route_data.get("node_path", []),
        )

    def _route_eta(
        self,
        graph,
        route_edges: list,
        current_edge: Optional[str] = None,
    ) -> float:
        """Calculate ETA for a route using current dynamic edge weights."""
        if not route_edges:
            return 0.0

        start_index = 0
        if current_edge and current_edge in route_edges:
            start_index = route_edges.index(current_edge)

        total = 0.0

        for edge_id in route_edges[start_index:]:
            edge = graph.edges.get(edge_id)
            if not edge:
                continue

            weight = float(
                edge.get(
                    "current_time_sec",
                    edge.get("base_time_sec", 0.0),
                )
                or 0.0
            )

            if weight == float("inf"):
                return float("inf")

            total += max(0.0, weight)

        return total

    def _capture_navigation_routes(self, affected_edges: set[str]) -> dict:
        """Capture each active navigation's current route before mutation."""
        from routing_engine.service import RoutingService

        graph = self.graph_manager.get_graph()
        if not graph:
            return {}

        snapshot = {}
        active_navs = NavigationSession.objects.filter(
            status=NavigationSession.Status.ACTIVE
        )

        routing_service = RoutingService()

        for nav in active_navs:
            current_position = nav.current_position or nav.source or {}
            destination = nav.destination or {}

            current_lat = current_position.get("lat")
            current_lng = current_position.get("lng")
            dest_lat = destination.get("lat")
            dest_lng = destination.get("lng")

            if None in (current_lat, current_lng, dest_lat, dest_lng):
                continue

            try:
                route_result = routing_service.compute_route(
                    float(current_lat),
                    float(current_lng),
                    float(dest_lat),
                    float(dest_lng),
                    mode="walking",
                    algorithm="astar",
                )
            except Exception as exc:
                logger.warning(
                    "Pre-change route calculation failed for %s: %s",
                    nav.id,
                    exc,
                )
                continue

            if not route_result.get("success"):
                continue

            route_data = route_result["data"]
            route_edges = self._route_edges_from_result(
                graph,
                route_data,
            )

            if not set(route_edges).intersection(affected_edges):
                continue

            snapshot[str(nav.id)] = {
                "navigation_id": str(nav.id),
                "route_id": nav.route_id,
                "route_edges": route_edges,
                "old_eta": float(
                    route_data.get("duration_sec", 0.0) or 0.0
                ),
                "current_position": dict(current_position),
                "destination": dict(destination),
                "current_edge": nav.current_edge,
            }

        return snapshot

    def _evaluate_and_reroute(
        self,
        snapshot: dict,
        changed_edges: set[str],
    ) -> list[dict]:
        """Evaluate affected routes and trigger reroute when threshold is met."""
        from routing_engine.service import RoutingService

        graph = self.graph_manager.get_graph()
        if not graph:
            return []

        results = []
        routing_service = RoutingService()

        for navigation_id, state in snapshot.items():
            affected_route_edges = set(state["route_edges"]).intersection(
                changed_edges
            )
            if not affected_route_edges:
                continue

            old_eta = float(state["old_eta"] or 0.0)
            if old_eta <= 0:
                continue

            new_eta = self._route_eta(
                graph,
                state["route_edges"],
                state.get("current_edge"),
            )

            trigger_edge = next(iter(affected_route_edges))

            decision = self.analyzer.should_reroute(
                navigation_id=navigation_id,
                old_eta=old_eta,
                new_eta=new_eta,
                edge_id=trigger_edge,
                route_edges=state["route_edges"],
            )

            logger.info(
                "Traffic analyzer: navigation=%s edge=%s old_eta=%.2f new_eta=%.2f decision=%s",
                navigation_id,
                trigger_edge,
                old_eta,
                new_eta,
                decision,
            )

            if not decision.get("should_reroute"):
                results.append({
                    "navigation_id": navigation_id,
                    "rerouted": False,
                    "decision": decision,
                })
                continue

            position = state["current_position"]
            destination = state["destination"]

            try:
                reroute_result = routing_service.reroute(
                    route_id=state["route_id"],
                    current_lat=float(position["lat"]),
                    current_lng=float(position["lng"]),
                    dest_lat=float(destination["lat"]),
                    dest_lng=float(destination["lng"]),
                    reason=f"traffic_change:{trigger_edge}",
                )
            except Exception as exc:
                logger.exception(
                    "Reroute calculation failed for navigation %s: %s",
                    navigation_id,
                    exc,
                )
                continue

            if not reroute_result.get("success"):
                logger.warning(
                    "Reroute unsuccessful for navigation %s: %s",
                    navigation_id,
                    reroute_result.get("error"),
                )
                continue

            route_data = reroute_result["data"]

            nav = NavigationSession.objects.filter(
                id=navigation_id,
                status=NavigationSession.Status.ACTIVE,
            ).first()

            if nav:
                nav.route_id = route_data["route_id"]
                nav.current_position = position
                nav.current_edge = nav.current_edge
                nav.save(update_fields=[
                    "route_id",
                    "current_position",
                    "current_edge",
                ])

            self._broadcast_route_changed(
                navigation_id=navigation_id,
                route_id=route_data["route_id"],
                reason=f"traffic_change:{trigger_edge}",
                eta_sec=route_data["duration_sec"],
                path=route_data["path"],
            )

            results.append({
                "navigation_id": navigation_id,
                "rerouted": True,
                "decision": decision,
                "route": route_data,
            })

        return results

    # ------------------------------------------------------------------
    # WEBSOCKET BROADCASTS
    # ------------------------------------------------------------------

    def _broadcast_traffic_update(
        self,
        edge_id: str,
        active_count: int,
        traffic_level: str,
        current_time: float,
    ):
        """Broadcast traffic changes to active navigation WebSocket groups."""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            active_navs = NavigationSession.objects.filter(
                status=NavigationSession.Status.ACTIVE
            )

            version = self.get_traffic_version()

            for nav in active_navs:
                async_to_sync(channel_layer.group_send)(
                    f"navigation_{nav.id}",
                    {
                        "type": "traffic_update",
                        "edge_id": edge_id,
                        "active_user_count": active_count,
                        "traffic_level": traffic_level,
                        "current_time_sec": current_time,
                        "traffic_version": version,
                    },
                )

        except Exception as exc:
            logger.warning(
                "Failed to broadcast traffic update: %s",
                exc,
            )

    def _broadcast_route_changed(
        self,
        navigation_id: str,
        route_id: str,
        reason: str,
        eta_sec: float,
        path: list,
    ):
        """Broadcast a route change to one navigation session."""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            async_to_sync(channel_layer.group_send)(
                f"navigation_{navigation_id}",
                {
                    "type": "route_changed",
                    "route_id": route_id,
                    "reason": reason,
                    "eta_sec": eta_sec,
                    "path": path,
                    "traffic_version": self.get_traffic_version(),
                    "map_version": self.graph_manager.get_map_version(),
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to broadcast route change: %s",
                exc,
            )

    # ------------------------------------------------------------------
    # REAL TELEMETRY
    # ------------------------------------------------------------------

    def process_telemetry(
        self,
        session_id: str,
        lat: float,
        lng: float,
        timestamp: Optional[str] = None,
        navigation_id: Optional[str] = None,
    ) -> dict:
        """Process real GPS telemetry through the traffic pipeline."""
        start_time = time.perf_counter()

        graph = self.graph_manager.get_graph()
        if not graph or not graph.spatial_index:
            return {
                "success": False,
                "error": "Graph not available",
            }

        matcher = MapMatcher(graph.spatial_index)
        match = matcher.match(lat, lng)

        if not match:
            return {
                "success": False,
                "error": "No matching road found",
            }

        edge_id = match["edge_id"]
        previous_edge = self.presence.get_session_edge(session_id)

        affected_edges = {edge_id}
        if previous_edge:
            affected_edges.add(previous_edge)

        # Capture active routes before mutating traffic weights.
        snapshot = self._capture_navigation_routes(affected_edges)

        presence_result = self.presence.update_presence(
            session_id,
            edge_id,
            lat,
            lng,
        )

        if not presence_result["success"]:
            return presence_result

        # Keep the navigation session synchronized when this telemetry
        # belongs to an active navigation session.
        if navigation_id:
            try:
                from navigation.services import NavigationService

                NavigationService().update_location(
                    navigation_id=navigation_id,
                    lat=lat,
                    lng=lng,
                    edge_id=edge_id,
                )
            except Exception as exc:
                logger.warning(
                    "Navigation location sync failed: %s",
                    exc,
                )

        changed_edges = set()

        # Recalculate every affected edge so moving users also reduce
        # traffic on their previous edge.
        for affected_edge in affected_edges:
            count = self.presence.get_edge_count(affected_edge)
            edge = graph.edges.get(affected_edge)

            if not edge:
                continue

            old_time = float(
                edge.get(
                    "current_time_sec",
                    edge.get("base_time_sec", 0.0),
                )
                or 0.0
            )
            old_level = edge.get("traffic_level", "LOW")

            new_time = self.weights.update_edge_weight(
                edge,
                count,
            )
            new_level = edge.get("traffic_level", "LOW")
            factor = edge.get("traffic_factor", 1.0)

            self._set_exact_edge_weight(
                affected_edge,
                new_time,
                traffic_level=new_level,
                traffic_factor=factor,
            )

            changed = (
                old_level != new_level
                or (
                    old_time != float("inf")
                    and abs(old_time - float(new_time)) > 0.01
                )
            )

            if changed:
                changed_edges.add(affected_edge)
                self._increment_traffic_version()
                self.analytics.record_traffic_state_change()

                self._broadcast_traffic_update(
                    edge_id=affected_edge,
                    active_count=count,
                    traffic_level=new_level,
                    current_time=new_time,
                )

        if changed_edges:
            self._evaluate_and_reroute(
                snapshot,
                changed_edges,
            )

        self.analytics.record_telemetry()

        processing_time = (
            time.perf_counter() - start_time
        ) * 1000

        current_edge = graph.edges.get(edge_id, {})

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": self.presence.get_edge_count(edge_id),
            "traffic_level": current_edge.get(
                "traffic_level",
                "LOW",
            ),
            "current_time_sec": current_edge.get(
                "current_time_sec",
                0,
            ),
            "match_confidence": match.get(
                "confidence",
                "LOW",
            ),
            "match_distance_m": match.get(
                "distance_m",
                0,
            ),
            "processing_time_ms": round(
                processing_time,
                2,
            ),
            "traffic_version": self.get_traffic_version(),
        }

    # ------------------------------------------------------------------
    # MANUAL SIMULATOR
    # ------------------------------------------------------------------

    def apply_manual_traffic(
        self,
        edge_id: str,
        traffic_level: str,
    ) -> dict:
        """Apply a manual traffic-level simulation through the full pipeline."""
        normalized = str(traffic_level).strip().upper()

        if normalized not in self.SPEEDS_KMH:
            return {
                "success": False,
                "error": f"Invalid traffic level: {traffic_level}",
            }

        snapshot = self._capture_navigation_routes({edge_id})
        update = self._apply_manual_level(edge_id, normalized)

        if not update["success"]:
            return update

        if update["changed"]:
            self._increment_traffic_version()
            self.analytics.record_traffic_state_change()

            self._broadcast_traffic_update(
                edge_id=edge_id,
                active_count=update["active_users"],
                traffic_level=update["traffic_level"],
                current_time=update["current_time_sec"],
            )

            reroutes = self._evaluate_and_reroute(
                snapshot,
                {edge_id},
            )
        else:
            reroutes = []

        update["traffic_version"] = self.get_traffic_version()
        update["simulated"] = True
        update["reroutes"] = reroutes

        return update

    # ------------------------------------------------------------------
    # SIMULATED USERS
    # ------------------------------------------------------------------

    def _get_simulated_sessions(self, edge_id: str) -> list[str]:
        client = get_redis_client()
        if not client:
            return []

        try:
            members = client.smembers(
                f"active_users:{edge_id}"
            )
            result = []

            for member in members:
                session_id = (
                    member.decode()
                    if isinstance(member, bytes)
                    else member
                )

                if session_id.startswith("sim_"):
                    result.append(session_id)

            return result
        except Exception as exc:
            logger.warning(
                "Unable to read simulated sessions: %s",
                exc,
            )
            return []

    def add_simulated_users(
        self,
        edge_id: str,
        count: int = 1,
    ) -> dict:
        """Add simulated users to an edge and recalculate traffic."""
        graph = self.graph_manager.get_graph()

        if not graph or edge_id not in graph.edges:
            return {
                "success": False,
                "error": "Edge not found",
            }

        try:
            count = max(1, min(int(count), 100))
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "count must be an integer",
            }

        snapshot = self._capture_navigation_routes({edge_id})

        for index in range(count):
            session_id = (
                f"sim_{edge_id}_"
                f"{int(time.time() * 1000)}_"
                f"{index}"
            )

            presence = self.presence.update_presence(
                session_id,
                edge_id,
                0.0,
                0.0,
            )

            if not presence["success"]:
                return presence

        active_count = self.presence.get_edge_count(edge_id)
        edge = graph.edges[edge_id]

        old_level = edge.get("traffic_level", "LOW")
        old_time = float(
            edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )
            or 0.0
        )

        new_time = self.weights.update_edge_weight(
            edge,
            active_count,
        )
        new_level = edge.get("traffic_level", "LOW")
        factor = edge.get("traffic_factor", 1.0)

        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=new_level,
            traffic_factor=factor,
        )

        changed = (
            old_level != new_level
            or (
                old_time != float("inf")
                and abs(old_time - float(new_time)) > 0.01
            )
        )

        reroutes = []

        if changed:
            self._increment_traffic_version()
            self.analytics.record_traffic_state_change()

            self._broadcast_traffic_update(
                edge_id=edge_id,
                active_count=active_count,
                traffic_level=new_level,
                current_time=new_time,
            )

            reroutes = self._evaluate_and_reroute(
                snapshot,
                {edge_id},
            )

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": active_count,
            "traffic_level": new_level,
            "current_time_sec": new_time,
            "traffic_version": self.get_traffic_version(),
            "simulated": True,
            "reroutes": reroutes,
        }

    def remove_simulated_users(
        self,
        edge_id: str,
        count: Optional[int] = None,
    ) -> dict:
        """Remove simulated users from an edge and recalculate traffic."""
        graph = self.graph_manager.get_graph()

        if not graph or edge_id not in graph.edges:
            return {
                "success": False,
                "error": "Edge not found",
            }

        client = get_redis_client()
        if not client:
            return {
                "success": False,
                "error": "Redis unavailable",
            }

        sim_sessions = self._get_simulated_sessions(edge_id)

        if count is None:
            selected = sim_sessions
        else:
            try:
                selected = sim_sessions[: max(0, int(count))]
            except (TypeError, ValueError):
                return {
                    "success": False,
                    "error": "count must be an integer",
                }

        snapshot = self._capture_navigation_routes({edge_id})

        for session_id in selected:
            client.srem(
                f"active_users:{edge_id}",
                session_id,
            )
            client.delete(
                f"session:{session_id}"
            )

        active_count = self.presence.get_edge_count(edge_id)
        edge = graph.edges[edge_id]

        old_level = edge.get("traffic_level", "LOW")
        old_time = float(
            edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )
            or 0.0
        )

        new_time = self.weights.update_edge_weight(
            edge,
            active_count,
        )
        new_level = edge.get("traffic_level", "LOW")
        factor = edge.get("traffic_factor", 1.0)

        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=new_level,
            traffic_factor=factor,
        )

        changed = (
            old_level != new_level
            or (
                old_time != float("inf")
                and abs(old_time - float(new_time)) > 0.01
            )
        )

        reroutes = []

        if changed:
            self._increment_traffic_version()
            self.analytics.record_traffic_state_change()

            self._broadcast_traffic_update(
                edge_id=edge_id,
                active_count=active_count,
                traffic_level=new_level,
                current_time=new_time,
            )

            reroutes = self._evaluate_and_reroute(
                snapshot,
                {edge_id},
            )

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": active_count,
            "traffic_level": new_level,
            "current_time_sec": new_time,
            "traffic_version": self.get_traffic_version(),
            "simulated": True,
            "removed": len(selected),
            "reroutes": reroutes,
        }

    def reset_simulation(self) -> dict:
        """Remove all simulated users and restore traffic from real presence."""
        client = get_redis_client()

        if client:
            keys = client.keys("active_users:*")

            for key in keys:
                members = client.smembers(key)

                for member in members:
                    session_id = (
                        member.decode()
                        if isinstance(member, bytes)
                        else member
                    )

                    if session_id.startswith("sim_"):
                        client.srem(key, session_id)
                        client.delete(
                            f"session:{session_id}"
                        )

        graph = self.graph_manager.get_graph()

        if graph:
            for edge_id, edge in graph.edges.items():
                active_count = self.presence.get_edge_count(edge_id)
                new_time = self.weights.update_edge_weight(
                    edge,
                    active_count,
                )
                self._set_exact_edge_weight(
                    edge_id,
                    new_time,
                    traffic_level=edge.get(
                        "traffic_level",
                        "LOW",
                    ),
                    traffic_factor=edge.get(
                        "traffic_factor",
                        1.0,
                    ),
                )

        version = self._increment_traffic_version()

        return {
            "success": True,
            "simulated": True,
            "traffic_version": version,
        }

    # ------------------------------------------------------------------
    # READ API
    # ------------------------------------------------------------------

    def get_traffic_state(self, edge_id: str) -> dict:
        """Get current traffic state for one edge."""
        graph = self.graph_manager.get_graph()

        if not graph:
            return {
                "success": False,
                "error": "Graph not available",
            }

        edge = graph.edges.get(edge_id)
        if not edge:
            return {
                "success": False,
                "error": "Edge not found",
            }

        active_count = self.presence.get_edge_count(edge_id)
        state = self.weights.get_edge_state(
            edge,
            active_count,
        )

        state["traffic_level"] = edge.get(
            "traffic_level",
            state.get("traffic_level", "LOW"),
        )
        state["current_time_sec"] = edge.get(
            "current_time_sec",
            state.get("current_time_sec", 0.0),
        )

        return {
            "success": True,
            "data": state,
        }

    def get_all_traffic(self) -> dict:
        """Get current traffic states for all active edges."""
        graph = self.graph_manager.get_graph()

        if not graph:
            return {
                "success": False,
                "error": "Graph not available",
            }

        active_edges = self.presence.get_all_active_edges()
        result = {}

        for edge_id, count in active_edges.items():
            edge = graph.edges.get(edge_id)
            if not edge:
                continue

            state = self.weights.get_edge_state(
                edge,
                count,
            )
            state["traffic_level"] = edge.get(
                "traffic_level",
                state.get("traffic_level", "LOW"),
            )
            state["current_time_sec"] = edge.get(
                "current_time_sec",
                state.get("current_time_sec", 0.0),
            )
            state["geometry"] = self._get_edge_geometry(
                graph,
                edge_id,
            )

            result[edge_id] = state

        return {
            "success": True,
            "data": {
                "edges": result,
                "traffic_version": self.get_traffic_version(),
                "active_edge_count": len(result),
            },
        }

    def _get_edge_geometry(self, graph, edge_id: str) -> Optional[dict]:
        """Return a simple LineString geometry for an edge."""
        edge = graph.edges.get(edge_id)
        if not edge:
            return None

        from_node = graph.nodes.get(edge.get("from"))
        to_node = graph.nodes.get(edge.get("to"))

        if not from_node or not to_node:
            return None

        return {
            "type": "LineString",
            "coordinates": [
                [from_node["lng"], from_node["lat"]],
                [to_node["lng"], to_node["lat"]],
            ],
        }

    def stop_sharing(self, session_id: str) -> dict:
        """Stop real-user presence and restore affected edge weight."""
        previous_edge = self.presence.get_session_edge(session_id)
        result = self.presence.remove_presence(session_id)

        if not result["success"]:
            return result

        if previous_edge:
            graph = self.graph_manager.get_graph()
            if graph and previous_edge in graph.edges:
                edge = graph.edges[previous_edge]
                active_count = self.presence.get_edge_count(previous_edge)
                new_time = self.weights.update_edge_weight(
                    edge,
                    active_count,
                )
                self._set_exact_edge_weight(
                    previous_edge,
                    new_time,
                    traffic_level=edge.get(
                        "traffic_level",
                        "LOW",
                    ),
                    traffic_factor=edge.get(
                        "traffic_factor",
                        1.0,
                    ),
                )

                self._increment_traffic_version()

        return {
            "success": True,
            "session_id": session_id,
        }

