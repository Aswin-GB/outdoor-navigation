"""
Tests for A* pathfinding algorithm.
"""
import pytest
from routing_engine.astar import astar, haversine_m, heuristic


def create_test_graph():
    """Create a simple test graph."""
    return {
        'nodes': {
            'A': {'id': 'A', 'lat': 0.0, 'lng': 0.0},
            'B': {'id': 'B', 'lat': 0.0, 'lng': 0.001},
            'C': {'id': 'C', 'lat': 0.001, 'lng': 0.001},
            'D': {'id': 'D', 'lat': 0.001, 'lng': 0.0},
        },
        'adjacency': {
            'A': [('B', 'e1', 100), ('D', 'e3', 150)],
            'B': [('A', 'e1r', 100), ('C', 'e2', 100)],
            'C': [('B', 'e2r', 100), ('D', 'e4', 100)],
            'D': [('C', 'e4r', 100), ('A', 'e3r', 150)],
        },
    }


class TestAstar:
    """Test A* algorithm."""

    def test_valid_route(self):
        """Test finding a valid route."""
        graph = create_test_graph()
        result = astar(graph, 'A', 'C')
        assert result is not None
        assert result['path'][0] == 'A'
        assert result['path'][-1] == 'C'
        assert result['algorithm'] == 'A*'
        assert result['distance_m'] > 0
        assert result['duration_sec'] > 0

    def test_same_source_dest(self):
        """Test route from node to itself."""
        graph = create_test_graph()
        result = astar(graph, 'A', 'A')
        assert result is not None
        assert result['path'] == ['A']
        assert result['distance_m'] == 0

    def test_unreachable_route(self):
        """Test unreachable destination."""
        graph = create_test_graph()
        # Add isolated node
        graph['nodes']['E'] = {'id': 'E', 'lat': 1.0, 'lng': 1.0}
        result = astar(graph, 'A', 'E')
        assert result is None

    def test_empty_graph(self):
        """Test with empty graph."""
        graph = {'nodes': {}, 'adjacency': {}}
        result = astar(graph, 'A', 'B')
        assert result is None

    def test_dynamic_weights(self):
        """Test A* with dynamic edge weights."""
        graph = create_test_graph()

        # Make direct path expensive
        def expensive_weight(edge_id):
            if edge_id == 'e1':
                return 1000
            return 100

        result = astar(graph, 'A', 'C', current_time_func=expensive_weight)
        assert result is not None
        # Should prefer A -> D -> C (250) over A -> B -> C (1100)
        assert 'D' in result['path']

    def test_heuristic_admissible(self):
        """Test that heuristic never overestimates."""
        h = heuristic(0.0, 0.0, 0.001, 0.001)
        actual = haversine_m(0.0, 0.0, 0.001, 0.001) / (5.0 * 1000 / 3600)
        assert h <= actual * 1.01  # Small tolerance for floating point

    def test_haversine_distance(self):
        """Test haversine distance calculation."""
        d = haversine_m(0.0, 0.0, 0.0, 0.001)
        assert 100 < d < 200  # Approximately 111m

    def test_route_fields(self):
        """Test that route response has all required fields."""
        graph = create_test_graph()
        result = astar(graph, 'A', 'C')
        assert 'route_id' in result
        assert 'path' in result
        assert 'coordinates' in result
        assert 'distance_m' in result
        assert 'duration_sec' in result
        assert 'algorithm' in result
        assert 'latency_ms' in result
        assert 'nodes_executed' in result
