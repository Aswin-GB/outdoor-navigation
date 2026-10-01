"""
Navigation session services.
"""
import uuid
from datetime import datetime
from typing import Optional
from navigation.models import NavigationSession


class NavigationService:
    """Manages navigation sessions."""

    def start_navigation(self, route_id: str, source: dict, destination: dict) -> dict:
        """Start a new navigation session."""
        session = NavigationSession.objects.create(
            route_id=route_id,
            source=source,
            destination=destination,
            status=NavigationSession.Status.ACTIVE,
        )
        return {
            'success': True,
            'navigation_id': str(session.id),
            'route_id': route_id,
            'status': session.status,
            'started_at': session.started_at.isoformat(),
        }

    def update_location(self, navigation_id: str, lat: float, lng: float, edge_id: str = None) -> dict:
        """Update navigation session with current location."""
        try:
            session = NavigationSession.objects.get(id=navigation_id)
            session.current_position = {'lat': lat, 'lng': lng}
            if edge_id:
                session.current_edge = edge_id
            session.save()
            return {
                'success': True,
                'navigation_id': navigation_id,
                'current_edge': edge_id,
            }
        except NavigationSession.DoesNotExist:
            return {'success': False, 'error': 'Navigation session not found'}

    def stop_navigation(self, navigation_id: str) -> dict:
        """Stop a navigation session."""
        try:
            session = NavigationSession.objects.get(id=navigation_id)
            session.status = NavigationSession.Status.STOPPED
            session.save()
            return {
                'success': True,
                'navigation_id': navigation_id,
                'status': 'stopped',
            }
        except NavigationSession.DoesNotExist:
            return {'success': False, 'error': 'Navigation session not found'}

    def get_session(self, navigation_id: str) -> Optional[NavigationSession]:
        """Get a navigation session by ID."""
        try:
            return NavigationSession.objects.get(id=navigation_id)
        except NavigationSession.DoesNotExist:
            return None
