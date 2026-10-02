"""
Navigation session services.
"""
from typing import Optional

from navigation.models import NavigationSession


class NavigationService:
    """Manages navigation sessions."""

    def start_navigation(
        self,
        route_id: str,
        source: dict,
        destination: dict,
        route_nodes: list | None = None,
        route_edges: list | None = None,
        duration_sec: float = 0.0,
    ) -> dict:

        session = NavigationSession.objects.create(
            route_id=route_id,
            source=source or {},
            destination=destination or {},
            current_position=source or {},
            route_nodes=route_nodes or [],
            route_edges=route_edges or [],
            current_eta_sec=float(duration_sec or 0.0),
            status=NavigationSession.Status.ACTIVE,
        )

        return {
            "success": True,
            "navigation_id": str(session.id),
            "route_id": route_id,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
        }

    def update_location(
        self,
        navigation_id: str,
        lat: float,
        lng: float,
        edge_id: str | None = None,
        current_eta_sec: float | None = None,
    ) -> dict:

        try:
            session = NavigationSession.objects.get(
                id=navigation_id
            )

            session.current_position = {
                "lat": float(lat),
                "lng": float(lng),
            }

            if edge_id:
                session.current_edge = edge_id

            if current_eta_sec is not None:
                session.current_eta_sec = float(
                    current_eta_sec
                )

            session.save()

            return {
                "success": True,
                "navigation_id": navigation_id,
                "current_edge": session.current_edge,
                "current_eta_sec": session.current_eta_sec,
            }

        except NavigationSession.DoesNotExist:
            return {
                "success": False,
                "error": "Navigation session not found",
            }

    def stop_navigation(self, navigation_id: str) -> dict:
        try:
            session = NavigationSession.objects.get(
                id=navigation_id
            )

            session.status = NavigationSession.Status.STOPPED
            session.save()

            return {
                "success": True,
                "navigation_id": navigation_id,
                "status": "stopped",
            }

        except NavigationSession.DoesNotExist:
            return {
                "success": False,
                "error": "Navigation session not found",
            }

    def get_session(
        self,
        navigation_id: str,
    ) -> Optional[NavigationSession]:

        try:
            return NavigationSession.objects.get(
                id=navigation_id
            )
        except NavigationSession.DoesNotExist:
            return None