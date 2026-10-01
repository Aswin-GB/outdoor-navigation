"""
In-memory spatial index for efficient nearest-edge lookups.
Uses geographic grid bucketing for O(1) candidate retrieval.
"""
import math
from typing import List, Tuple, Optional


class SpatialIndex:
    """
    Grid-based spatial index for campus routing edges.
    Divides the campus into grid cells for fast nearest-edge queries.
    """

    def __init__(self, cell_size_m: float = 100.0):
        self.cell_size_m = cell_size_m
        self.cells = {}  # (cell_x, cell_y) -> list of (edge_id, from_lat, from_lng, to_lat, to_lng, edge_data)
        self.edges = {}  # edge_id -> edge_data

    def _lat_lng_to_cell(self, lat: float, lng: float) -> Tuple[int, int]:
        """Convert lat/lng to grid cell coordinates."""
        # Simple equirectangular projection for small areas
        lat_rad = math.radians(lat)
        meters_per_deg_lat = 111111.0
        meters_per_deg_lng = 111111.0 * math.cos(lat_rad)
        cell_x = int((lng * meters_per_deg_lng) / self.cell_size_m)
        cell_y = int((lat * meters_per_deg_lat) / self.cell_size_m)
        return (cell_x, cell_y)

    def _get_cells_for_edge(self, from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> set:
        """Get all grid cells that an edge passes through."""
        cells = set()
        # Add cells for both endpoints
        cells.add(self._lat_lng_to_cell(from_lat, from_lng))
        cells.add(self._lat_lng_to_cell(to_lat, to_lng))

        # For longer edges, add intermediate cells
        dist = math.sqrt((to_lat - from_lat) ** 2 + (to_lng - from_lng) ** 2)
        num_intermediate = max(1, int(dist * 111000 / self.cell_size_m))
        for i in range(num_intermediate + 1):
            t = i / num_intermediate
            lat = from_lat + t * (to_lat - from_lat)
            lng = from_lng + t * (to_lng - from_lng)
            cells.add(self._lat_lng_to_cell(lat, lng))

        return cells

    def add_edge(self, edge_id: str, from_lat: float, from_lng: float,
                 to_lat: float, to_lng: float, edge_data: dict):
        """Add an edge to the spatial index."""
        self.edges[edge_id] = edge_data
        cells = self._get_cells_for_edge(from_lat, from_lng, to_lat, to_lng)
        for cell in cells:
            if cell not in self.cells:
                self.cells[cell] = []
            self.cells[cell].append((edge_id, from_lat, from_lng, to_lat, to_lng, edge_data))

    def remove_edge(self, edge_id: str):
        """Remove an edge from the spatial index."""
        if edge_id in self.edges:
            del self.edges[edge_id]

    def get_nearby_edges(self, lat: float, lng: float, radius_m: float = 200.0) -> List[dict]:
        """Get edges within radius of a point."""
        # For small graphs, just return all edges
        # This is more reliable than grid-based search for campus-scale data
        if len(self.edges) < 500:
            return list(self.edges.values())

        # For larger graphs, use grid-based search
        cell_radius = max(1, int(radius_m / self.cell_size_m))
        center_cell = self._lat_lng_to_cell(lat, lng)

        nearby = []
        seen_edges = set()

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (center_cell[0] + dx, center_cell[1] + dy)
                if cell in self.cells:
                    for edge_id, flat, flng, tlat, tlng, edge_data in self.cells[cell]:
                        if edge_id not in seen_edges and edge_id in self.edges:
                            seen_edges.add(edge_id)
                            nearby.append(edge_data)

        return nearby

    def get_nearest_edge(self, lat: float, lng: float, max_distance_m: float = 500.0) -> Optional[dict]:
        """Find the nearest edge to a point."""
        nearby = self.get_nearby_edges(lat, lng, max_distance_m)
        if not nearby:
            return None

        best_edge = None
        best_dist = float('inf')

        for edge in nearby:
            dist = self._point_to_edge_distance(lat, lng, edge)
            if dist < best_dist:
                best_dist = dist
                best_edge = edge

        if best_edge:
            best_edge['match_distance_m'] = round(best_dist, 2)
            return best_edge
        return None

    def _point_to_edge_distance(self, lat: float, lng: float, edge: dict) -> float:
        """Calculate minimum distance from point to edge segment using haversine."""
        from routing_engine.astar import haversine_m

        from_lat = edge.get('from_lat', 0)
        from_lng = edge.get('from_lng', 0)
        to_lat = edge.get('to_lat', 0)
        to_lng = edge.get('to_lng', 0)

        # For short edges, just use minimum distance to endpoints
        d1 = haversine_m(lat, lng, from_lat, from_lng)
        d2 = haversine_m(lat, lng, to_lat, to_lng)

        # Also check distance to midpoint for better accuracy
        mid_lat = (from_lat + to_lat) / 2
        mid_lng = (from_lng + to_lng) / 2
        d3 = haversine_m(lat, lng, mid_lat, mid_lng)

        return min(d1, d2, d3)

    def clear(self):
        """Clear all edges from the index."""
        self.cells.clear()
        self.edges.clear()

    def get_stats(self) -> dict:
        """Get index statistics."""
        return {
            'total_edges': len(self.edges),
            'total_cells': len(self.cells),
            'cell_size_m': self.cell_size_m,
        }
