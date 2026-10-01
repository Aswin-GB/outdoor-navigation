"""
Dynamic edge weight calculator.
Updates edge weights based on traffic state.
"""
import logging
from traffic.scoring import TrafficScorer

logger = logging.getLogger('traffic')


class WeightCalculator:
    """Calculates dynamic edge weights based on traffic."""

    def __init__(self):
        self.scorer = TrafficScorer()

    def update_edge_weight(self, edge: dict, active_users: int) -> float:
        """
        Update an edge's current_time_sec based on traffic.
        Returns the new current_time_sec.
        """
        base_time = edge.get('base_time_sec', 0)
        capacity = edge.get('capacity')  # May be None

        new_time = self.scorer.calculate_current_time(base_time, active_users, capacity)

        # Update edge in place
        edge['current_time_sec'] = new_time
        edge['traffic_level'] = self.scorer.classify_by_count(active_users)
        edge['traffic_factor'] = self.scorer.calculate_congestion_factor(
            self.scorer.calculate_crowd_ratio(active_users, capacity)
        )

        return new_time

    def get_edge_state(self, edge: dict, active_users: int) -> dict:
        """Get the current traffic state for an edge."""
        base_time = edge.get('base_time_sec', 0)
        capacity = edge.get('capacity')

        state = self.scorer.get_traffic_state(active_users, capacity)
        state['base_time_sec'] = base_time
        state['current_time_sec'] = self.scorer.calculate_current_time(base_time, active_users, capacity)
        state['edge_id'] = edge.get('id')

        return state
