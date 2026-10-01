"""
A* pathfinding algorithm for campus routing.
"""
import heapq
import math
import time
import uuid
from typing import Optional


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in meters between two points."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def heuristic(node_lat: float, node_lng: float, goal_lat: float, goal_lng: float) -> float:
    """
    Admissible heuristic for A*.
    Uses haversine distance divided by maximum walking speed (5 km/h).
    This never overestimates the actual travel time.
    """
    dist = haversine_m(node_lat, node_lng, goal_lat, goal_lng)
    max_speed_mps = 5.0 * 1000 / 3600  # 5 km/h in m/s
    return dist / max_speed_mps


def astar(
    graph: dict,
    start_node: str,
    goal_node: str,
    current_time_func=None,
) -> Optional[dict]:
    """
    A* pathfinding algorithm.

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
            'algorithm': 'A*',
            'latency_ms': 0.0,
        }

    goal_lat = nodes[goal_node]['lat']
    goal_lng = nodes[goal_node]['lng']

    # Priority queue: (f_score, counter, node_id)
    counter = 0
    open_set = [(heuristic(nodes[start_node]['lat'], nodes[start_node]['lng'], goal_lat, goal_lng), counter, start_node)]
    open_set_hash = {start_node}

    came_from = {}
    g_score = {start_node: 0.0}
    f_score = {start_node: heuristic(nodes[start_node]['lat'], nodes[start_node]['lng'], goal_lat, goal_lng)}

    nodes_executed = 0

    while open_set:
        _, _, current = heapq.heappop(open_set)
        open_set_hash.discard(current)
        nodes_executed += 1

        if current == goal_node:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()

            # Build coordinate path
            coordinates = [[nodes[n]['lng'], nodes[n]['lat']] for n in path]

            # Calculate total distance
            total_distance = 0.0
            for i in range(len(path) - 1):
                n1, n2 = path[i], path[i + 1]
                for neighbor, edge_id, weight in adjacency.get(n1, []):
                    if neighbor == n2:
                        total_distance += weight
                        break

            latency = (time.perf_counter() - start_time) * 1000

            return {
                'route_id': str(uuid.uuid4()),
                'path': path,
                'coordinates': coordinates,
                'distance_m': round(total_distance, 2),
                'duration_sec': round(g_score[goal_node], 2),
                'nodes_executed': nodes_executed,
                'algorithm': 'A*',
                'latency_ms': round(latency, 3),
            }

        for neighbor, edge_id, base_weight in adjacency.get(current, []):
            # Use dynamic weight if available
            if current_time_func:
                weight = current_time_func(edge_id)
            else:
                weight = base_weight

            tentative_g = g_score[current] + weight

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(nodes[neighbor]['lat'], nodes[neighbor]['lng'], goal_lat, goal_lng)
                f_score[neighbor] = f

                if neighbor not in open_set_hash:
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))
                    open_set_hash.add(neighbor)

    # No path found
    return None
