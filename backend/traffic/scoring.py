"""
Traffic scoring module.
Determines traffic level based on active user count and capacity.
"""
import logging
from django.conf import settings

logger = logging.getLogger('traffic')


class TrafficScorer:
    """
    Deterministic traffic scoring based on crowd density.
    Uses configurable thresholds and capacity-based ratios.
    """

    def __init__(self):
        self.thresholds = settings.TRAFFIC_THRESHOLDS
        self.default_capacity = 10  # Default fallback capacity

    def classify_by_count(self, active_users: int) -> str:
        """
        Classify traffic level based on active user count.
        Uses prototype thresholds from settings.
        """
        for level, (low, high) in self.thresholds.items():
            if low <= active_users <= high:
                return level
        return 'SEVERE'

    def calculate_crowd_ratio(self, active_users: int, capacity: int = None) -> float:
        """Calculate crowd ratio (active_users / capacity)."""
        if capacity is None:
            capacity = self.default_capacity
        if capacity <= 0:
            return 0.0
        return active_users / capacity

    def calculate_congestion_factor(self, crowd_ratio: float) -> float:
        """
        Calculate congestion factor from crowd ratio.
        Deterministic formula: 1.0 + (crowd_ratio * 2.0)
        This means:
        - 0% capacity -> 1.0x (free flow)
        - 50% capacity -> 2.0x (moderate slowdown)
        - 100% capacity -> 3.0x (heavy congestion)
        - 150% capacity -> 4.0x (severe congestion)
        """
        return 1.0 + (crowd_ratio * 2.0)

    def calculate_current_time(self, base_time_sec: float, active_users: int, capacity: int = None) -> float:
        """
        Calculate current travel time based on crowd.
        Formula: current_time = base_time * congestion_factor
        """
        ratio = self.calculate_crowd_ratio(active_users, capacity)
        factor = self.calculate_congestion_factor(ratio)
        return round(base_time_sec * factor, 2)

    def get_traffic_state(self, active_users: int, capacity: int = None) -> dict:
        """Get complete traffic state for an edge."""
        level = self.classify_by_count(active_users)
        ratio = self.calculate_crowd_ratio(active_users, capacity)
        factor = self.calculate_congestion_factor(ratio)

        return {
            'active_users': active_users,
            'traffic_level': level,
            'crowd_ratio': round(ratio, 3),
            'congestion_factor': round(factor, 3),
            'capacity': capacity or self.default_capacity,
        }
