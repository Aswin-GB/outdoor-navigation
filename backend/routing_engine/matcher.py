"""
Map matching module for GPS telemetry.
Matches GPS points to the nearest routing edge.
"""
from typing import Optional
from routing_engine.spatial_index import SpatialIndex
from routing_engine.astar import haversine_m


class MapMatcher:
    """Matches GPS coordinates to routing edges using spatial index."""

    def __init__(self, spatial_index: SpatialIndex):
        self.spatial_index = spatial_index

    def match(self, lat: float, lng: float, max_distance_m: float = 100.0) -> Optional[dict]:
        """
        Match a GPS point to the nearest routing edge.

        Returns:
            Dict with edge_id, distance, and match confidence or None
        """
        edge = self.spatial_index.get_nearest_edge(lat, lng, max_distance_m)
        if edge is None:
            return None

        distance = edge.get('match_distance_m', float('inf'))

        # Calculate match confidence based on distance
        if distance < 10:
            confidence = 'HIGH'
        elif distance < 30:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        return {
            'edge_id': edge['id'],
            'distance_m': distance,
            'confidence': confidence,
            'edge_name': edge.get('name', ''),
            'road_type': edge.get('road_type', ''),
        }

    def match_with_fallback(self, lat: float, lng: float, max_distance_m: float = 200.0) -> Optional[dict]:
        """Match with increasing radius if no match found."""
        for radius in [50, 100, 150, 200]:
            result = self.match(lat, lng, radius)
            if result:
                return result
        return None
