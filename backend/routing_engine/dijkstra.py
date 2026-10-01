"""
Dijkstra's algorithm for campus routing.
"""
import heapq
import time
import uuid
from typing import Optional

def dijkstra(
    graph: dict,
    start_node: str,
    goal_node: str,
    current_time_func=None,
) -> Optional[dict]:
    """
    Dijkstra's shortest path algorithm.

    Args:
        graph: Dict with 'nodes' (dict of node_id -> {lat, lng}) and
               'adjacency' (dict of node_id -> [(neighbor_id, edge_id, weight)])
        start_node: Starting node ID
        goal_node: Goal node ID
        current_time_func: Optional function(edge_id) -> current_time_sec for dynamic weights

    Returns:
        Dict with path, distance, duration, nodes_executed or None if no route
    """
    start_time = time.perf_counter()

    nodes = graph.get('nodes', {})
    adjacency = graph.get('adjacency', {})

    if start_node not in nodes or goal_node not in nodes:
        return None

    if start_node == goal_node:
        return {
            'route_id': str(uuid.uuid4()),
            'path': [start_node],
            'coordinates': [[nodes[start_node]['lng'], nodes[start_node]['lat']]],
            'distance_m': 0.0,
            'duration_sec': 0.0,
            'nodes_executed': 1,
            'algorithm': 'Dijkstra',
            'latency_ms': 0.0,
        }

    # Priority queue: (distance, node_id)
    open_set = [(0.0, start_node)]
    came_from = {}
    g_score = {start_node: 0.0}
    nodes_executed = 0

    while open_set:
        current_dist, current = heapq.heappop(open_set)
        nodes_executed += 1

        if current == goal_node:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()

            coordinates = [[nodes[n]['lng'], nodes[n]['lat']] for n in path]

            total_distance = 0.0
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i + 1]
                for neighbor, edge_id, weight in adjacency.get(n1, []):
                    if neighbor == n2:
                        edge_data = graph.get('edges', {}).get(edge_id, {})
                        total_distance += edge_data.get('distance_m', 0.0)
                        break

            latency = (time.perf_counter() - start_time) * 1000

            return {
                'route_id': str(uuid.uuid4()),
                'path': path,
                'coordinates': coordinates,
                'distance_m': round(total_distance, 2),
                'duration_sec': round(g_score[goal_node], 2),
                'nodes_executed': nodes_executed,
                'algorithm': 'Dijkstra',
                'latency_ms': round(latency, 3),
            }

        if current_dist > g_score.get(current, float('inf')):
            continue

        for neighbor, edge_id, base_weight in adjacency.get(current, []):
            weight = current_time_func(edge_id) if current_time_func else base_weight
            tentative_g = g_score[current] + weight

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heapq.heappush(open_set, (tentative_g, neighbor))

    return None
