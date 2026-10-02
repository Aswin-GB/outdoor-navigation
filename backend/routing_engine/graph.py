"""
Graph data structures and utilities for campus routing.
"""
import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in meters."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    x = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))


class GraphData:
    """In-memory representation of the campus routing graph."""

    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.adjacency = {}
        self.spatial_index = None
        self.graph_version = 0
        self.map_version = 0

    def build_adjacency(self):
        """Build adjacency list from current edge weights."""
        self.adjacency = {}

        for edge_id, edge in self.edges.items():
            from_node = edge["from"]
            to_node = edge["to"]

            weight = edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )

            self.adjacency.setdefault(from_node, []).append(
                (to_node, edge_id, weight)
            )

    def build_spatial_index(self):
        """Build spatial index for map matching."""
        from routing_engine.spatial_index import SpatialIndex

        self.spatial_index = SpatialIndex(cell_size_m=100.0)

        for edge_id, edge in self.edges.items():
            from_node = self.nodes.get(edge["from"])
            to_node = self.nodes.get(edge["to"])

            if not from_node or not to_node:
                continue

            edge_data = dict(edge)
            edge_data["from_lat"] = from_node["lat"]
            edge_data["from_lng"] = from_node["lng"]
            edge_data["to_lat"] = to_node["lat"]
            edge_data["to_lng"] = to_node["lng"]

            self.spatial_index.add_edge(
                edge_id,
                from_node["lat"],
                from_node["lng"],
                to_node["lat"],
                to_node["lng"],
                edge_data,
            )

    def get_edge_weight_func(self):
        """Return current dynamic edge weights."""

        def weight_func(edge_id):
            edge = self.edges.get(edge_id)

            if not edge:
                return float("inf")

            return edge.get(
                "current_time_sec",
                edge.get("base_time_sec", 0.0),
            )

        return weight_func

    def set_edge_travel_time(
        self,
        edge_id: str,
        travel_time_sec: float,
        traffic_level: str | None = None,
        traffic_factor: float | None = None,
    ):
        """
        Set the exact dynamic travel time.

        This is different from update_edge_weight(), which previously
        interpreted its second parameter as a traffic level string.
        """
        if edge_id not in self.edges:
            return False

        edge = self.edges[edge_id]

        edge["current_time_sec"] = float(travel_time_sec)

        if traffic_level is not None:
            edge["traffic_level"] = traffic_level

        if traffic_factor is not None:
            edge["traffic_factor"] = float(traffic_factor)

        from_node = edge["from"]

        if from_node in self.adjacency:
            for index, (neighbor, eid, _) in enumerate(
                self.adjacency[from_node]
            ):
                if eid == edge_id:
                    self.adjacency[from_node][index] = (
                        neighbor,
                        eid,
                        float(travel_time_sec),
                    )
                    break

        return True

    def update_edge_weight(self, edge_id: str, traffic_level: str):
        """
        Backward-compatible traffic-level update.
        """
        if edge_id not in self.edges:
            return False

        speeds = {
            "LOW": 40,
            "MODERATE": 30,
            "MEDIUM": 30,
            "HIGH": 18,
            "SEVERE": 7,
            "CLOSED": 0,
        }

        edge = self.edges[edge_id]
        distance = float(edge.get("distance_m", 0.0))
        speed_kmh = speeds.get(traffic_level, 30)

        if speed_kmh == 0:
            travel_time = float("inf")
        else:
            travel_time = distance / (speed_kmh * 1000 / 3600)

        return self.set_edge_travel_time(
            edge_id,
            travel_time,
            traffic_level=traffic_level,
        )

    def get_stats(self):
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "graph_version": self.graph_version,
            "map_version": self.map_version,
        }