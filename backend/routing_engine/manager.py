"""
GraphManager - Singleton manager for the in-memory routing graph.
Loads graph from JSON files and keeps it in memory for fast access.
"""
import json
import logging
import threading
from pathlib import Path
from typing import Optional

from django.conf import settings
from routing_engine.graph import GraphData

logger = logging.getLogger('routing')

_graph_instance = None
_lock = threading.Lock()


class GraphManager:
    """
    Manages the in-memory routing graph.
    Implements singleton pattern to ensure single graph instance.
    """

    def __init__(self):
        self._graph: Optional[GraphData] = None
        self._graph_version = 0
        self._map_version = 0
        self._stale = False
        self._lock = threading.RLock()

    def load_graph(self) -> GraphData:
        """Load graph from JSON files into memory."""
        with self._lock:
            graph = GraphData()

            # Load nodes
            nodes_path = settings.NODES_JSON_PATH
            if nodes_path.exists():
                with open(nodes_path) as f:
                    nodes_data = json.load(f)
                for node in nodes_data.get('nodes', []):
                    graph.nodes[node['id']] = {
                        'id': node['id'],
                        'lat': node['lat'],
                        'lng': node['lng'],
                    }
                logger.info(f"Loaded {len(graph.nodes)} nodes from {nodes_path}")
            else:
                logger.warning(f"Nodes file not found: {nodes_path}")

            # Load edges
            edges_path = settings.EDGES_JSON_PATH
            if edges_path.exists():
                with open(edges_path) as f:
                    edges_data = json.load(f)
                for edge in edges_data.get('edges', []):
                    graph.edges[edge['id']] = edge
                logger.info(f"Loaded {len(graph.edges)} edges from {edges_path}")
            else:
                logger.warning(f"Edges file not found: {edges_path}")

            # Build adjacency and spatial index
            graph.build_adjacency()
            graph.build_spatial_index()

            # Load map version from database
            try:
                from mapdata.models import MapVersion
                mv = MapVersion.objects.first()
                if mv:
                    graph.map_version = mv.version
                    self._map_version = mv.version
            except Exception:
                pass

            graph.graph_version = self._graph_version
            self._graph = graph

            logger.info(f"Graph loaded: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
            return graph

    def get_graph(self) -> Optional[GraphData]:
        """Get the current in-memory graph."""
        if self._graph is None or self._stale or self.is_graph_stale():
            self._stale = False
            return self.reload_graph()
        return self._graph

    def reload_graph(self) -> GraphData:
        """Force reload the graph from disk."""
        with self._lock:
            self._graph_version += 1
            logger.info(f"Reloading graph, version {self._graph_version}")
            return self.load_graph()

    def get_graph_version(self) -> int:
        """Get current graph version."""
        return self._graph_version

    def get_map_version(self) -> int:
        """Get current map version."""
        return self._map_version

    def is_graph_stale(self) -> bool:
        """Check if graph needs reload (map version changed)."""
        try:
            from mapdata.models import MapVersion
            mv = MapVersion.objects.first()
            if mv and mv.version != self._map_version:
                return True
        except Exception:
            pass
        return False

    def mark_stale(self):
        """Mark the graph as stale, triggering reload on next access."""
        self._stale = True
        self._graph_version += 1

    def refresh_from_db(self) -> GraphData:
        """Reload the graph from disk and update map version metadata."""
        with self._lock:
            self._stale = False
            return self.load_graph()

    def reload_if_stale(self) -> GraphData:
        """Reload graph if it has become stale."""
        if self._stale or self.is_graph_stale():
            self._stale = False  # Reset stale flag after reload
            return self.reload_graph()
        return self._graph

    def ensure_current(self) -> GraphData:
        """Ensure the graph is current, reloading if necessary."""
        return self.reload_if_stale()

    def update_edge_weight(self, edge_id: str, traffic_level: str):
        """Update edge weight in the in-memory graph based on traffic level."""
        if self._graph:
            self._graph.update_edge_weight(edge_id, traffic_level)


    def get_spatial_index(self):
        """Get the spatial index for map matching."""
        if self._graph:
            return self._graph.spatial_index
        return None

    def get_stats(self) -> dict:
        """Get graph statistics."""
        if self._graph:
            return self._graph.get_stats()
        return {'node_count': 0, 'edge_count': 0, 'graph_version': 0, 'map_version': 0}


def get_graph_manager() -> GraphManager:
    """Get the singleton GraphManager instance."""
    global _graph_instance
    if _graph_instance is None:
        with _lock:
            if _graph_instance is None:
                _graph_instance = GraphManager()
    return _graph_instance


# Module-level convenience functions
def load_graph() -> GraphData:
    return get_graph_manager().load_graph()


def get_graph() -> Optional[GraphData]:
    return get_graph_manager().get_graph()


def reload_graph() -> GraphData:
    return get_graph_manager().reload_graph()


def get_graph_version() -> int:
    return get_graph_manager().get_graph_version()


def is_graph_stale() -> bool:
    return get_graph_manager().is_graph_stale()
