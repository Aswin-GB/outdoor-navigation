"""
API views for traffic telemetry and traffic simulation.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from traffic.service import TrafficService

logger = logging.getLogger("traffic")


class TelemetryView(APIView):
    """POST /api/v1/telemetry/location - Submit GPS telemetry."""

    def post(self, request):
        data = request.data

        session_id = data.get("session_id")
        navigation_id = data.get("navigation_id")
        lat = data.get("lat")
        lng = data.get("lng")
        timestamp = data.get("timestamp")

        if not session_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_SESSION",
                        "message": "session_id is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if lat is None or lng is None:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "lat and lng are required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Coordinates must be valid numbers.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Coordinates out of range.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = TrafficService().process_telemetry(
                session_id=session_id,
                lat=lat,
                lng=lng,
                timestamp=timestamp,
                navigation_id=navigation_id,
            )
        except Exception as exc:
            logger.exception("Telemetry processing failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "TELEMETRY_INTERNAL_ERROR",
                        "message": "Failed to process telemetry.",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result.get("success")
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class TrafficStopView(APIView):
    """POST /api/v1/telemetry/stop - Stop sharing location."""

    def post(self, request):
        session_id = request.data.get("session_id")

        if not session_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_SESSION",
                        "message": "session_id is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = TrafficService().stop_sharing(session_id)

        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result.get("success")
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class TrafficSimulatorView(APIView):
    """
    POST /api/v1/traffic/simulate

    Payload:
        {"action": "add", "edge_id": "...", "count": 5}
        {"action": "remove", "edge_id": "...", "count": 2}
        {"action": "reset"}
    """

    def post(self, request):
        action = str(request.data.get("action", "")).strip().lower()
        edge_id = request.data.get("edge_id")
        raw_count = request.data.get("count", 1)

        service = TrafficService()

        if action == "reset":
            result = service.reset_simulation()

        elif action == "add":
            if not edge_id:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_EDGE",
                            "message": "edge_id is required.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_COUNT",
                            "message": "count must be an integer.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = service.add_simulated_users(
                edge_id=edge_id,
                count=count,
            )

        elif action == "remove":
            if not edge_id:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_EDGE",
                            "message": "edge_id is required.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_COUNT",
                            "message": "count must be an integer.",
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = service.remove_simulated_users(
                edge_id=edge_id,
                count=count,
            )

        else:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_ACTION",
                        "message": (
                            "action must be add, remove, or reset."
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result.get("success")
                else status.HTTP_400_BAD_REQUEST
            ),
        )
