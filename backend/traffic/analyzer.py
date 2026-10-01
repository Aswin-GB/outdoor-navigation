"""
Route impact analyzer.
Determines when traffic changes should trigger rerouting.
"""
import logging
import time
from typing import Optional
from django.conf import settings

logger = logging.getLogger('traffic')


class RouteImpactAnalyzer:
    """
    Analyzes whether traffic changes impact active routes
    and determines if rerouting is needed.
    """

    def __init__(self):
        self.reroute_threshold = settings.REROUTE_THRESHOLD_PERCENT
        self.min_reroute_interval = settings.MIN_REROUTE_INTERVAL_SECONDS
        self.max_staleness = settings.MAX_TRAFFIC_STALENESS_SECONDS
        self._last_reroute = {}  # navigation_id -> timestamp

    def should_reroute(
        self,
        navigation_id: str,
        old_eta: float,
        new_eta: float,
        edge_id: str,
        route_edges: list,
    ) -> dict:
        """
        Determine if rerouting should be triggered.

        Returns dict with should_reroute bool and reason.
        """
        # Check if edge is part of the active route
        if edge_id not in route_edges:
            return {
                'should_reroute': False,
                'reason': 'edge_not_on_route',
            }

        # Check minimum reroute interval
        last_time = self._last_reroute.get(navigation_id, 0)
        if time.time() - last_time < self.min_reroute_interval:
            return {
                'should_reroute': False,
                'reason': 'min_interval_not_met',
            }

        # Calculate ETA change percentage
        if old_eta <= 0:
            return {
                'should_reroute': False,
                'reason': 'invalid_eta',
            }

        eta_change_pct = ((new_eta - old_eta) / old_eta) * 100

        if eta_change_pct >= self.reroute_threshold:
            self._last_reroute[navigation_id] = time.time()
            return {
                'should_reroute': True,
                'reason': 'threshold_exceeded',
                'eta_change_pct': round(eta_change_pct, 2),
            }

        return {
            'should_reroute': False,
            'reason': 'below_threshold',
            'eta_change_pct': round(eta_change_pct, 2),
        }

    def record_reroute(self, navigation_id: str):
        """Record that a reroute was triggered."""
        self._last_reroute[navigation_id] = time.time()

    def is_stale(self, last_update_time: float) -> bool:
        """Check if traffic data is stale."""
        return (time.time() - last_update_time) > self.max_staleness
