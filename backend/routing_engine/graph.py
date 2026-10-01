"""
Graph data structures and utilities for campus routing.
"""
import json
import math
from pathlib import Path
from typing import Optional


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in meters."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


class GraphData:
    """In-memory representation of the campus routing graph."""

    def __init__(self):
        self.nodes = {}  # node_id -> {id, lat, lng}
        self.edges = {}  # edge_id -> {id, from, to, distance_m, base_time_sec, ...}
        self.adjacency = {}  # node_id -> [(neighbor_id, edge_id, weight)]
        self.spatial_index = None
        self.graph_version = 0
        self.map_version = 0

    def build_adjacency(self):
        """Build adjacency list from edges."""
        self.adjacency = {}
        for edge_id, edge in self.edges.items():
            from_node = edge['from']
            to_node = edge['to']
            weight = edge.get('current_time_sec', edge.get('base_time_sec', 0))

            if from_node not in self.adjacency:
                self.adjacency[from_node] = []
            self.adjacency[from_node].append((to_node, edge_id, weight))

    def build_spatial_index(self):
        """Build spatial index for map matching."""
        from routing_engine.spatial_index import SpatialIndex
        self.spatial_index = SpatialIndex(cell_size_m=100.0)

        for edge_id, edge in self.edges.items():
            from_node = self.nodes.get(edge['from'])
            to_node = self.nodes.get(edge['to'])
            if from_node and to_node:
                edge_data = dict(edge)
                edge_data['from_lat'] = from_node['lat']
                edge_data['from_lng'] = from_node['lng']
                edge_data['to_lat'] = to_node['lat']
                edge_data['to_lng'] = to_node['lng']
                self.spatial_index.add_edge(
                    edge_id,
                    from_node['lat'], from_node['lng'],
                    to_node['lat'], to_node['lng'],
                    edge_data
                )

    def get_edge_weight_func(self):
        """Return a function that gets current edge weight for A*."""
        def weight_func(edge_id):
            edge = self.edges.get(edge_id)
            if edge:
                return edge.get('current_time_sec', edge.get('base_time_sec', 0))
            return float('inf')
        return weight_func

    def update_edge_weight(self, edge_id: str, new_time_sec: float):
        """Update the current travel time for an edge."""
        if edge_id in self.edges:
            self.edges[edge_id]['current_time_sec'] = new_time_sec
            # Update adjacency weights
            edge = self.edges[edge_id]
            from_node = edge['from']
            if from_node in self.adjacency:
                for i, (neighbor, eid, weight) in enumerate(self.adjacency[from_node]):
                    if eid == edge_id:
                        self.adjacency[from_node][i] = (neighbor, eid, new_time_sec)
                        break

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return {
            'node_count': len(self.nodes),
            'edge_count': len(self.edges),
            'graph_version': self.graph_version,
            'map_version': self.map_version,
        }
