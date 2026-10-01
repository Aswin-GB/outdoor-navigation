"""
Tests for spatial index.
"""
import pytest
from routing_engine.spatial_index import SpatialIndex


class TestSpatialIndex:
    """Test spatial index."""

    def setup_method(self):
        self.index = SpatialIndex(cell_size_m=100.0)

    def test_add_and_find_edge(self):
        edge = {'id': 'e1', 'name': 'Test Road'}
        self.index.add_edge('e1', 9.57, 77.68, 9.58, 77.69, edge)

        result = self.index.get_nearest_edge(9.575, 77.685, max_distance_m=1000.0)
        assert result is not None
        assert result['id'] == 'e1'

    def test_no_edge_found(self):
        result = self.index.get_nearest_edge(0.0, 0.0)
        assert result is None

    def test_get_nearby_edges(self):
        edge1 = {'id': 'e1', 'name': 'Road 1'}
        edge2 = {'id': 'e2', 'name': 'Road 2'}
        self.index.add_edge('e1', 9.57, 77.68, 9.58, 77.69, edge1)
        self.index.add_edge('e2', 9.571, 77.681, 9.572, 77.682, edge2)

        nearby = self.index.get_nearby_edges(9.575, 77.685, radius_m=500)
        assert len(nearby) >= 1

    def test_stats(self):
        edge = {'id': 'e1'}
        self.index.add_edge('e1', 9.57, 77.68, 9.58, 77.69, edge)
        stats = self.index.get_stats()
        assert stats['total_edges'] == 1
        assert stats['total_cells'] > 0
