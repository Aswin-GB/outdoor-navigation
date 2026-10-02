"""
Traffic service - complete production-safe traffic pipeline.

Handles:
- Redis/Valkey presence tracking
- crowd-based traffic scoring
- dynamic edge weights
- manual traffic simulation
- simulated users
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
    """Main traffic processing service."""

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
        self._traffic_version += 1
        try:
            client = get_redis_client()
            if client:
                client.set("traffic_version", self._traffic_version)
        except Exception as exc:
            logger.warning("Unable to persist traffic version: %s", exc)
        return self._traffic_version

    # ------------------------------------------------------------------
    # GRAPH / WEIGHT HELPERS
    # ------------------------------------------------------------------

    def _set_exact_edge_weight(
        self,
        edge_id: str,
        current_time_sec: float,
        traffic_level: Optional[str] = None,
        traffic_factor: Optional[float] = None,
    ) -> bool:
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
        for index, (neighbor, eid, _) in enumerate(
            graph.adjacency.get(from_node, [])
        ):
            if eid == edge_id:
                graph.adjacency[from_node][index] = (
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

    def _apply_manual_level(self, edge_id: str, traffic_level: str) -> dict:
        graph = self.graph_manager.get_graph()
        if not graph:
            return {"success": False, "error": "Graph not available"}

        edge = graph.edges.get(edge_id)
        if not edge:
            return {"success": False, "error": "Edge not found"}

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

        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=level,
            traffic_factor=factor,
        )

        changed = (
            old_level != level
            or old_time != new_time
        )

        active_users = self.presence.get_edge_count(edge_id)

        return {
            "success": True,
            "changed": changed,
            "edge_id": edge_id,
            "previous_traffic_level": old_level,
            "traffic_level": level,
            "previous_time_sec": old_time,
            "current_time_sec": new_time,
            "traffic_factor": factor,
            "active_users": active_users,
            "geometry": self._get_edge_geometry(graph, edge_id),
        }

    # ------------------------------------------------------------------
    # ROUTE HELPERS
    # ------------------------------------------------------------------

    def _nodes_to_edges(self, graph, node_path: list) -> list:
        edge_path = []
        for index in range(max(0, len(node_path) - 1)):
            from_node = node_path[index]
            to_node = node_path[index + 1]
            selected = None
            for neighbor, edge_id, _weight in graph.adjacency.get(from_node, []):
                if neighbor == to_node:
                    selected = edge_id
                    break
            if selected is None:
                return []
            edge_path.append(selected)
        return edge_path

    def _route_edges_from_result(self, graph, route_data: dict) -> list:
        edge_path = route_data.get("edge_path")
        if isinstance(edge_path, list) and edge_path:
            return edge_path
        return self._nodes_to_edges(graph, route_data.get("node_path", []))

    def _route_eta(
        self,
        graph,
        route_edges: list,
        current_edge: Optional[str] = None,
    ) -> float:
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
        """Capture active route state before traffic mutation."""
        graph = self.graph_manager.get_graph()
        if not graph:
            return {}

        snapshot = {}
        active_navs = NavigationSession.objects.filter(
            status=NavigationSession.Status.ACTIVE
        )

        for nav in active_navs:
            stored_edges = list(nav.route_edges or [])
            stored_nodes = list(nav.route_nodes or [])

            if stored_edges and not set(stored_edges).intersection(affected_edges):
                continue

            # Some older sessions may not have persisted route edges.
            if not stored_edges:
                try:
                    from routing_engine.service import RoutingService

                    position = nav.current_position or nav.source or {}
                    destination = nav.destination or {}
                    route_result = RoutingService().compute_route(
                        float(position["lat"]),
                        float(position["lng"]),
                        float(destination["lat"]),
                        float(destination["lng"]),
                        mode="walking",
                        algorithm="astar",
                    )
                    if not route_result.get("success"):
                        continue
                    data = route_result["data"]
                    stored_edges = self._route_edges_from_result(graph, data)
                    stored_nodes = data.get("node_path", [])
                except Exception as exc:
                    logger.warning(
                        "Unable to reconstruct navigation route %s: %s",
                        nav.id,
                        exc,
                    )
                    continue

                if not set(stored_edges).intersection(affected_edges):
                    continue

            old_eta = float(nav.current_eta_sec or 0.0)
            if old_eta <= 0:
                old_eta = self._route_eta(graph, stored_edges, nav.current_edge)

            snapshot[str(nav.id)] = {
                "navigation_id": str(nav.id),
                "route_id": nav.route_id,
                "route_edges": stored_edges,
                "route_nodes": stored_nodes,
                "old_eta": old_eta,
                "current_position": dict(
                    nav.current_position or nav.source or {}
                ),
                "destination": dict(nav.destination or {}),
                "current_edge": nav.current_edge,
            }

        return snapshot

    def _evaluate_and_reroute(self, snapshot: dict, changed_edges: set[str]) -> list[dict]:
        """Run route-impact analysis and reroute only affected sessions."""
        from routing_engine.service import RoutingService

        graph = self.graph_manager.get_graph()
        if not graph:
            return []

        results = []
        routing_service = RoutingService()

        for navigation_id, state in snapshot.items():
            affected = set(state["route_edges"]).intersection(changed_edges)
            if not affected:
                continue

            old_eta = float(state.get("old_eta", 0.0) or 0.0)
            if old_eta <= 0:
                continue

            new_eta = self._route_eta(
                graph,
                state["route_edges"],
                state.get("current_edge"),
            )
            trigger_edge = next(iter(affected))

            decision = self.analyzer.should_reroute(
                navigation_id=navigation_id,
                old_eta=old_eta,
                new_eta=new_eta,
                edge_id=trigger_edge,
                route_edges=state["route_edges"],
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

                if not reroute_result.get("success"):
                    results.append({
                        "navigation_id": navigation_id,
                        "rerouted": False,
                        "decision": decision,
                        "error": reroute_result.get("error"),
                    })
                    continue

                route_data = reroute_result["data"]

                nav = NavigationSession.objects.filter(
                    id=navigation_id,
                    status=NavigationSession.Status.ACTIVE,
                ).first()

                if nav:
                    nav.route_id = route_data["route_id"]
                    nav.route_nodes = route_data.get("node_path", [])
                    nav.route_edges = route_data.get("edge_path", [])
                    nav.current_eta_sec = float(route_data.get("duration_sec", 0.0))
                    nav.current_position = position
                    nav.save(update_fields=[
                        "route_id",
                        "route_nodes",
                        "route_edges",
                        "current_eta_sec",
                        "current_position",
                        "last_seen_at",
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

            except Exception as exc:
                logger.exception(
                    "Reroute failed for navigation %s: %s",
                    navigation_id,
                    exc,
                )
                results.append({
                    "navigation_id": navigation_id,
                    "rerouted": False,
                    "decision": decision,
                    "error": str(exc),
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
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            version = self.get_traffic_version()
            active_navs = NavigationSession.objects.filter(
                status=NavigationSession.Status.ACTIVE
            )

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
            logger.warning("Failed to broadcast traffic update: %s", exc)

    def _broadcast_route_changed(
        self,
        navigation_id: str,
        route_id: str,
        reason: str,
        eta_sec: float,
        path: list,
    ):
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
            logger.warning("Failed to broadcast route change: %s", exc)

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
        start_time = time.perf_counter()
        graph = self.graph_manager.get_graph()

        if not graph or not graph.spatial_index:
            return {"success": False, "error": "Graph not available"}

        match = MapMatcher(graph.spatial_index).match_with_fallback(lat, lng)
        if not match:
            return {"success": False, "error": "No matching road found"}

        edge_id = match["edge_id"]
        previous_edge = self.presence.get_session_edge(session_id)
        affected_edges = {edge_id}
        if previous_edge:
            affected_edges.add(previous_edge)

        snapshot = self._capture_navigation_routes(affected_edges)

        presence = self.presence.update_presence(
            session_id,
            edge_id,
            lat,
            lng,
        )
        if not presence.get("success"):
            return presence

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
                logger.warning("Navigation location sync failed: %s", exc)

        changed_edges = set()

        for affected_edge in affected_edges:
            edge = graph.edges.get(affected_edge)
            if not edge:
                continue

            count = self.presence.get_edge_count(affected_edge)
            old_level = edge.get("traffic_level", "LOW")
            old_time = float(
                edge.get(
                    "current_time_sec",
                    edge.get("base_time_sec", 0.0),
                )
                or 0.0
            )

            new_time = self.weights.update_edge_weight(edge, count)
            new_level = edge.get("traffic_level", "LOW")
            factor = edge.get("traffic_factor", 1.0)

            self._set_exact_edge_weight(
                affected_edge,
                new_time,
                traffic_level=new_level,
                traffic_factor=factor,
            )

            changed = old_level != new_level or abs(old_time - float(new_time)) > 0.01
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
            self._evaluate_and_reroute(snapshot, changed_edges)

        self.analytics.record_telemetry()
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        current = graph.edges.get(edge_id, {})

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": self.presence.get_edge_count(edge_id),
            "traffic_level": current.get("traffic_level", "LOW"),
            "current_time_sec": current.get("current_time_sec", 0.0),
            "match_confidence": match.get("confidence", "LOW"),
            "match_distance_m": match.get("distance_m", 0.0),
            "processing_time_ms": round(elapsed_ms, 2),
            "traffic_version": self.get_traffic_version(),
            "timestamp": timestamp,
        }

    # ------------------------------------------------------------------
    # MANUAL TRAFFIC
    # ------------------------------------------------------------------

    def apply_manual_traffic(self, edge_id: str, traffic_level: str) -> dict:
        normalized = str(traffic_level).strip().upper()
        if normalized not in self.SPEEDS_KMH:
            return {
                "success": False,
                "error": f"Invalid traffic level: {traffic_level}",
            }

        snapshot = self._capture_navigation_routes({edge_id})
        update = self._apply_manual_level(edge_id, normalized)
        if not update.get("success"):
            return update

        reroutes = []
        if update["changed"]:
            self._increment_traffic_version()
            self.analytics.record_traffic_state_change()
            self._broadcast_traffic_update(
                edge_id=edge_id,
                active_count=update["active_users"],
                traffic_level=update["traffic_level"],
                current_time=update["current_time_sec"],
            )
            reroutes = self._evaluate_and_reroute(snapshot, {edge_id})

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
            members = client.smembers(f"active_users:{edge_id}")
            result = []
            for member in members:
                session_id = (
                    member.decode() if isinstance(member, bytes) else member
                )
                if session_id.startswith("sim_"):
                    result.append(session_id)
            return result
        except Exception as exc:
            logger.warning("Unable to read simulated sessions: %s", exc)
            return []

    def add_simulated_users(self, edge_id: str, count: int = 1) -> dict:
        graph = self.graph_manager.get_graph()
        if not graph or edge_id not in graph.edges:
            return {"success": False, "error": "Edge not found"}

        try:
            count = max(1, min(int(count), 100))
        except (TypeError, ValueError):
            return {"success": False, "error": "count must be an integer"}

        snapshot = self._capture_navigation_routes({edge_id})

        for index in range(count):
            session_id = f"sim_{edge_id}_{int(time.time() * 1000)}_{index}"
            presence = self.presence.update_presence(
                session_id,
                edge_id,
                0.0,
                0.0,
            )
            if not presence.get("success"):
                return presence

        edge = graph.edges[edge_id]
        active_count = self.presence.get_edge_count(edge_id)
        old_level = edge.get("traffic_level", "LOW")
        old_time = float(
            edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )
            or 0.0
        )

        new_time = self.weights.update_edge_weight(edge, active_count)
        new_level = edge.get("traffic_level", "LOW")
        factor = edge.get("traffic_factor", 1.0)

        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=new_level,
            traffic_factor=factor,
        )

        changed = old_level != new_level or abs(old_time - float(new_time)) > 0.01
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
            reroutes = self._evaluate_and_reroute(snapshot, {edge_id})

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": active_count,
            "traffic_level": new_level,
            "current_time_sec": new_time,
            "traffic_factor": factor,
            "traffic_version": self.get_traffic_version(),
            "simulated": True,
            "added": count,
            "geometry": self._get_edge_geometry(graph, edge_id),
            "reroutes": reroutes,
        }

    def remove_simulated_users(
        self,
        edge_id: str,
        count: Optional[int] = None,
    ) -> dict:
        graph = self.graph_manager.get_graph()
        if not graph or edge_id not in graph.edges:
            return {"success": False, "error": "Edge not found"}

        client = get_redis_client()
        if not client:
            return {"success": False, "error": "Redis unavailable"}

        sessions = self._get_simulated_sessions(edge_id)
        if count is None:
            selected = sessions
        else:
            try:
                selected = sessions[: max(0, int(count))]
            except (TypeError, ValueError):
                return {"success": False, "error": "count must be an integer"}

        snapshot = self._capture_navigation_routes({edge_id})

        for session_id in selected:
            client.srem(f"active_users:{edge_id}", session_id)
            client.delete(f"session:{session_id}")

        edge = graph.edges[edge_id]
        active_count = self.presence.get_edge_count(edge_id)
        old_level = edge.get("traffic_level", "LOW")
        old_time = float(
            edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )
            or 0.0
        )

        new_time = self.weights.update_edge_weight(edge, active_count)
        new_level = edge.get("traffic_level", "LOW")
        factor = edge.get("traffic_factor", 1.0)
        self._set_exact_edge_weight(
            edge_id,
            new_time,
            traffic_level=new_level,
            traffic_factor=factor,
        )

        changed = old_level != new_level or abs(old_time - float(new_time)) > 0.01
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
            reroutes = self._evaluate_and_reroute(snapshot, {edge_id})

        return {
            "success": True,
            "edge_id": edge_id,
            "active_users": active_count,
            "traffic_level": new_level,
            "current_time_sec": new_time,
            "traffic_version": self.get_traffic_version(),
            "simulated": True,
            "removed": len(selected),
            "geometry": self._get_edge_geometry(graph, edge_id),
            "reroutes": reroutes,
        }

    def reset_simulation(self) -> dict:
        client = get_redis_client()
        if client:
            for key in client.keys("active_users:*"):
                members = client.smembers(key)
                for member in members:
                    session_id = (
                        member.decode() if isinstance(member, bytes) else member
                    )
                    if session_id.startswith("sim_"):
                        client.srem(key, session_id)
                        client.delete(f"session:{session_id}")

        graph = self.graph_manager.get_graph()
        if graph:
            changed_edges = set()
            for edge_id, edge in graph.edges.items():
                old_time = float(
                    edge.get(
                        "current_time_sec",
                        edge.get("base_time_sec", 0.0),
                    )
                    or 0.0
                )
                old_level = edge.get("traffic_level", "LOW")
                count = self.presence.get_edge_count(edge_id)
                new_time = self.weights.update_edge_weight(edge, count)
                new_level = edge.get("traffic_level", "LOW")
                factor = edge.get("traffic_factor", 1.0)
                self._set_exact_edge_weight(
                    edge_id,
                    new_time,
                    traffic_level=new_level,
                    traffic_factor=factor,
                )
                if old_level != new_level or abs(old_time - float(new_time)) > 0.01:
                    changed_edges.add(edge_id)

            if changed_edges:
                self.analytics.record_traffic_state_change()

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
        graph = self.graph_manager.get_graph()
        if not graph:
            return {"success": False, "error": "Graph not available"}

        edge = graph.edges.get(edge_id)
        if not edge:
            return {"success": False, "error": "Edge not found"}

        active_count = self.presence.get_edge_count(edge_id)
        state = self.weights.get_edge_state(edge, active_count)
        state["edge_id"] = edge_id
        state["name"] = edge.get("name") or edge_id
        state["active_users"] = active_count
        state["traffic_level"] = edge.get(
            "traffic_level",
            state.get("traffic_level", "LOW"),
        )
        state["current_time_sec"] = edge.get(
            "current_time_sec",
            state.get("current_time_sec", 0.0),
        )
        state["geometry"] = self._get_edge_geometry(graph, edge_id)

        return {
            "success": True,
            "data": state,
        }

    def get_all_traffic(self) -> dict:
        """
        Return all edges that have live users OR a non-LOW simulated/manual state.

        This is the production fix for the red traffic overlay: a manually
        changed HIGH/SEVERE edge must remain visible even when active_users=0.
        """
        graph = self.graph_manager.get_graph()
        if not graph:
            return {"success": False, "error": "Graph not available"}

        result = {}

        for edge_id, edge in graph.edges.items():
            active_count = self.presence.get_edge_count(edge_id)
            traffic_level = str(
                edge.get("traffic_level", "LOW")
            ).upper()

            if active_count <= 0 and traffic_level == "LOW":
                continue

            state = self.weights.get_edge_state(edge, active_count)
            state["edge_id"] = edge_id
            state["name"] = edge.get("name") or edge_id
            state["active_users"] = active_count
            state["traffic_level"] = traffic_level
            state["current_time_sec"] = edge.get(
                "current_time_sec",
                state.get("current_time_sec", 0.0),
            )
            state["traffic_factor"] = edge.get(
                "traffic_factor",
                state.get("congestion_factor", 1.0),
            )
            state["geometry"] = self._get_edge_geometry(graph, edge_id)

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
        previous_edge = self.presence.get_session_edge(session_id)
        result = self.presence.remove_presence(session_id)
        if not result.get("success"):
            return result

        if previous_edge:
            graph = self.graph_manager.get_graph()
            if graph and previous_edge in graph.edges:
                edge = graph.edges[previous_edge]
                active_count = self.presence.get_edge_count(previous_edge)
                old_level = edge.get("traffic_level", "LOW")
                old_time = float(
                    edge.get(
                        "current_time_sec",
                        edge.get("base_time_sec", 0.0),
                    )
                    or 0.0
                )
                new_time = self.weights.update_edge_weight(edge, active_count)
                self._set_exact_edge_weight(
                    previous_edge,
                    new_time,
                    traffic_level=edge.get("traffic_level", "LOW"),
                    traffic_factor=edge.get("traffic_factor", 1.0),
                )

                changed = (
                    old_level != edge.get("traffic_level", "LOW")
                    or abs(old_time - float(new_time)) > 0.01
                )
                if changed:
                    self._increment_traffic_version()
                    self.analytics.record_traffic_state_change()
                    self._broadcast_traffic_update(
                        edge_id=previous_edge,
                        active_count=active_count,
                        traffic_level=edge.get("traffic_level", "LOW"),
                        current_time=new_time,
                    )

        return {
            "success": True,
            "session_id": session_id,
            "traffic_version": self.get_traffic_version(),
        }
