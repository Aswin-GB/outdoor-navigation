"""
Routing service - orchestrates A* / Dijkstra pathfinding,
dynamic traffic weights, route caching and rerouting.
"""

import logging
import time
import uuid
from typing import Optional

from routing_engine.astar import astar, haversine_m
from routing_engine.dijkstra import dijkstra
from routing_engine.manager import get_graph_manager
from analytics.services import AnalyticsService

logger = logging.getLogger("routing")


class RoutingService:
    """
    Service responsible for:

    - nearest-node matching
    - A* / Dijkstra route computation
    - dynamic traffic-aware weights
    - route caching
    - route metadata
    - mid-journey rerouting
    """

    SUPPORTED_ALGORITHMS = {
        "astar": "A*",
        "dijkstra": "Dijkstra",
    }

    def __init__(self):
        self.graph_manager = get_graph_manager()
        self.analytics = AnalyticsService()
        self._redis_available = None

    # ------------------------------------------------------------------
    # CACHE
    # ------------------------------------------------------------------

    def _get_cache_key(
        self,
        source_node: str,
        dest_node: str,
        algorithm: str,
        map_version: int,
        traffic_version: int,
    ) -> str:
        """
        Generate a traffic-aware cache key.

        A route must become invalid when:
        - source changes
        - destination changes
        - algorithm changes
        - map changes
        - traffic changes
        """
        return (
            f"route:"
            f"{source_node}:"
            f"{dest_node}:"
            f"{algorithm}:"
            f"M{map_version}:"
            f"T{traffic_version}"
        )

    def _is_redis_available(self) -> bool:
        """Check whether Redis is reachable."""
        if self._redis_available is not None:
            return self._redis_available

        try:
            from cache.redis import get_redis_client

            client = get_redis_client()

            if client:
                client.ping()
                self._redis_available = True
            else:
                self._redis_available = False

        except Exception:
            self._redis_available = False

        return self._redis_available

    def _get_cached_route(
        self,
        cache_key: str,
    ) -> Optional[dict]:
        """Load a route from Redis cache."""
        try:
            from cache.redis import get_cached_item

            cached = get_cached_item(cache_key)

            if not cached:
                return None

            route = dict(cached)
            route["cache"] = "HIT"

            return route

        except Exception as exc:
            logger.warning(
                "Route cache read failed: %s",
                exc,
            )
            return None

    def _cache_route(
        self,
        cache_key: str,
        route: dict,
        ttl: int = 300,
    ):
        """Store route in Redis."""
        try:
            from cache.redis import set_cached_item

            set_cached_item(
                cache_key,
                route,
                ttl,
            )

        except Exception as exc:
            logger.warning(
                "Route cache write failed: %s",
                exc,
            )

    # ------------------------------------------------------------------
    # GRAPH / NODE HELPERS
    # ------------------------------------------------------------------

    def find_nearest_node(
        self,
        lat: float,
        lng: float,
        max_distance_m: float = 500.0,
    ) -> Optional[str]:
        """
        Find the nearest graph node.

        Returns None when no graph node is within the
        configured maximum distance.
        """
        graph = self.graph_manager.get_graph()

        if not graph or not graph.nodes:
            return None

        best_node = None
        best_distance = float("inf")

        for node_id, node in graph.nodes.items():
            distance = haversine_m(
                lat,
                lng,
                node["lat"],
                node["lng"],
            )

            if distance < best_distance:
                best_distance = distance
                best_node = node_id

        if (
            best_node is not None
            and best_distance <= max_distance_m
        ):
            return best_node

        return None

    def _build_edge_path(
        self,
        graph,
        node_path: list,
    ) -> list:
        """
        Convert a node path into the exact edge sequence
        selected by the routing algorithm.
        """
        edge_path = []

        if not node_path or len(node_path) < 2:
            return edge_path

        for index in range(len(node_path) - 1):
            from_node = node_path[index]
            to_node = node_path[index + 1]

            selected_edge = None

            for neighbor, edge_id, _weight in graph.adjacency.get(
                from_node,
                [],
            ):
                if neighbor == to_node:
                    selected_edge = edge_id
                    break

            if selected_edge is None:
                logger.warning(
                    "Could not resolve edge between nodes %s -> %s",
                    from_node,
                    to_node,
                )

                return []

            edge_path.append(selected_edge)

        return edge_path

    def _get_traffic_version(self) -> int:
        """Read the current traffic version."""
        try:
            from traffic.service import TrafficService

            return TrafficService().get_traffic_version()

        except Exception as exc:
            logger.warning(
                "Could not read traffic version: %s",
                exc,
            )
            return 0

    # ------------------------------------------------------------------
    # ROUTE COMPUTATION
    # ------------------------------------------------------------------

    def compute_route(
        self,
        source_lat: float,
        source_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "walking",
        algorithm: str = "astar",
    ) -> dict:
        """
        Compute the fastest traffic-aware route.
        """

        start_time = time.perf_counter()

        algorithm = (
            str(algorithm or "astar")
            .strip()
            .lower()
        )

        if algorithm not in self.SUPPORTED_ALGORITHMS:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_ALGORITHM",
                    "message": (
                        "algorithm must be one of: "
                        "astar, dijkstra."
                    ),
                },
            }

        # --------------------------------------------------------------
        # GRAPH
        # --------------------------------------------------------------

        graph = self.graph_manager.get_graph()

        if not graph:
            return {
                "success": False,
                "error": {
                    "code": "GRAPH_NOT_LOADED",
                    "message": (
                        "Routing graph is not loaded."
                    ),
                },
            }

        if not graph.nodes:
            return {
                "success": False,
                "error": {
                    "code": "EMPTY_GRAPH",
                    "message": (
                        "Routing graph contains no nodes."
                    ),
                },
            }

        # --------------------------------------------------------------
        # NEAREST SOURCE NODE
        # --------------------------------------------------------------

        source_node = self.find_nearest_node(
            float(source_lat),
            float(source_lng),
        )

        if source_node is None:
            return {
                "success": False,
                "error": {
                    "code": "SOURCE_UNREACHABLE",
                    "message": (
                        "No graph node found near "
                        "source location."
                    ),
                },
            }

        # --------------------------------------------------------------
        # NEAREST DESTINATION NODE
        # --------------------------------------------------------------

        dest_node = self.find_nearest_node(
            float(dest_lat),
            float(dest_lng),
        )

        if dest_node is None:
            return {
                "success": False,
                "error": {
                    "code": "DESTINATION_UNREACHABLE",
                    "message": (
                        "No graph node found near "
                        "destination location."
                    ),
                },
            }

        # --------------------------------------------------------------
        # VERSIONS
        # --------------------------------------------------------------

        map_version = self.graph_manager.get_map_version()
        traffic_version = self._get_traffic_version()

        cache_key = self._get_cache_key(
            source_node=source_node,
            dest_node=dest_node,
            algorithm=algorithm,
            map_version=map_version,
            traffic_version=traffic_version,
        )

        # --------------------------------------------------------------
        # CACHE LOOKUP
        # --------------------------------------------------------------

        cached = self._get_cached_route(cache_key)

        if cached:
            self.analytics.record_cache_hit()
            cached["source_node"] = source_node
            cached["dest_node"] = dest_node

            # Backward compatibility with older cache entries.
            if "source" not in cached:
                cached["source"] = {
                    "lat": float(source_lat),
                    "lng": float(source_lng),
                }

            if "destination" not in cached:
                cached["destination"] = {
                    "lat": float(dest_lat),
                    "lng": float(dest_lng),
                }

            if "edge_path" not in cached:
                cached["edge_path"] = self._build_edge_path(
                    graph,
                    cached.get("node_path", []),
                )

            return {
                "success": True,
                "data": cached,
            }

        self.analytics.record_cache_miss()

        # --------------------------------------------------------------
        # GRAPH DICT FOR ALGORITHM
        # --------------------------------------------------------------

        graph_dict = {
            "nodes": graph.nodes,
            "adjacency": graph.adjacency,
            "edges": graph.edges,
        }

        # IMPORTANT:
        # A* / Dijkstra reads the current dynamic edge weight
        # from graph.edges.
        current_time_func = (
            graph.get_edge_weight_func()
        )

        # --------------------------------------------------------------
        # ROUTING ALGORITHM
        # --------------------------------------------------------------

        if algorithm == "dijkstra":
            result = dijkstra(
                graph_dict,
                source_node,
                dest_node,
                current_time_func,
            )
        else:
            result = astar(
                graph_dict,
                source_node,
                dest_node,
                current_time_func,
            )

        if result is None:
            return {
                "success": False,
                "error": {
                    "code": "ROUTE_NOT_FOUND",
                    "message": (
                        "No walkable route exists "
                        "between source and destination."
                    ),
                },
            }

        # --------------------------------------------------------------
        # EDGE PATH
        # --------------------------------------------------------------

        node_path = result.get(
            "path",
            [],
        )

        edge_path = self._build_edge_path(
            graph,
            node_path,
        )

        if len(node_path) > 1 and not edge_path:
            return {
                "success": False,
                "error": {
                    "code": "EDGE_PATH_RESOLUTION_FAILED",
                    "message": (
                        "Route was found but the "
                        "edge sequence could not be resolved."
                    ),
                },
            }

        # --------------------------------------------------------------
        # METRICS
        # --------------------------------------------------------------

        algorithm_name = self.SUPPORTED_ALGORITHMS[
            algorithm
        ]

        if algorithm == "astar":
            self.analytics.record_astar_run(
                result.get("latency_ms", 0.0)
            )

        # --------------------------------------------------------------
        # ROUTE RESPONSE
        # --------------------------------------------------------------

        route_data = {
            "route_id": result.get(
                "route_id",
                str(uuid.uuid4()),
            ),

            # Geographic polyline
            "path": result.get(
                "coordinates",
                [],
            ),

            # Internal graph path
            "node_path": node_path,

            # Exact edges used by route
            "edge_path": edge_path,

            "distance_m": result.get(
                "distance_m",
                0.0,
            ),

            "duration_sec": result.get(
                "duration_sec",
                0.0,
            ),

            "algorithm": algorithm_name,
            "mode": mode,

            "cache": "MISS",

            "map_version": map_version,
            "traffic_version": traffic_version,

            "source": {
                "lat": float(source_lat),
                "lng": float(source_lng),
            },

            "destination": {
                "lat": float(dest_lat),
                "lng": float(dest_lng),
            },

            "source_node": source_node,
            "dest_node": dest_node,

            "latency_ms": result.get(
                "latency_ms",
                0.0,
            ),

            "nodes_executed": result.get(
                "nodes_executed",
                0,
            ),
        }

        # --------------------------------------------------------------
        # CACHE
        # --------------------------------------------------------------

        self._cache_route(
            cache_key,
            route_data,
        )

        # --------------------------------------------------------------
        # ROUTE METRICS
        # --------------------------------------------------------------

        total_latency = (
            time.perf_counter()
            - start_time
        ) * 1000

        self.analytics.record_route_request(
            total_latency
        )

        logger.info(
            "Route computed: %s -> %s | "
            "algorithm=%s | distance=%.2fm | "
            "duration=%.2fs | edges=%d | traffic_v=%s",
            source_node,
            dest_node,
            algorithm_name,
            route_data["distance_m"],
            route_data["duration_sec"],
            len(edge_path),
            traffic_version,
        )

        return {
            "success": True,
            "data": route_data,
        }

    # ------------------------------------------------------------------
    # REROUTING
    # ------------------------------------------------------------------

    def reroute(
        self,
        route_id: str,
        current_lat: float,
        current_lng: float,
        dest_lat: float,
        dest_lng: float,
        reason: str = "traffic_change",
    ) -> dict:
        """
        Compute a fresh route from the user's current position
        to the destination using the latest dynamic edge weights.

        The old route_id is retained as context.
        A new route_id is generated for the new route.
        """

        result = self.compute_route(
            source_lat=current_lat,
            source_lng=current_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            mode="walking",
            algorithm="astar",
        )

        if not result.get("success"):
            logger.warning(
                "Reroute failed for route %s: %s",
                route_id,
                result.get("error"),
            )

            return {
                "success": False,
                "error": result.get(
                    "error",
                    {
                        "code": "REROUTE_FAILED",
                        "message": (
                            "Unable to calculate "
                            "a new route."
                        ),
                    },
                ),
            }

        route_data = result["data"]

        route_data["rerouted"] = True
        route_data["previous_route_id"] = route_id
        route_data["reason"] = reason

        self.analytics.record_reroute()

        logger.info(
            "Route rerouted: old_route=%s "
            "new_route=%s reason=%s",
            route_id,
            route_data["route_id"],
            reason,
        )

        return {
            "success": True,
            "data": route_data,
        }