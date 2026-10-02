"""
API views for routing engine.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from routing_engine.service import RoutingService

logger = logging.getLogger("routing")


class RouteView(APIView):
    """POST /api/v1/routes - Compute the fastest route."""

    def post(self, request):
        data = request.data

        source = data.get("source") or {}
        source_lat = source.get("lat")
        source_lng = source.get("lng")

        if source_lat is None or source_lng is None:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_SOURCE",
                        "message": "Source coordinates are required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        destination = data.get("destination") or {}
        dest_place_id = destination.get("place_id")
        dest_lat = destination.get("lat")
        dest_lng = destination.get("lng")

        if dest_place_id is None and (
            dest_lat is None or dest_lng is None
        ):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_DESTINATION",
                        "message": (
                            "Destination place_id or coordinates are required."
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if dest_place_id and (
            dest_lat is None or dest_lng is None
        ):
            from places.models import Place

            try:
                place = Place.objects.get(id=dest_place_id)
                dest_lat = place.lat
                dest_lng = place.lng
            except Place.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "PLACE_NOT_FOUND",
                            "message": (
                                f"Place with id {dest_place_id} not found."
                            ),
                        },
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            source_lat = float(source_lat)
            source_lng = float(source_lng)
            dest_lat = float(dest_lat)
            dest_lng = float(dest_lng)
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

        if not (-90 <= source_lat <= 90) or not (-180 <= source_lng <= 180):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Source coordinates out of range.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (-90 <= dest_lat <= 90) or not (-180 <= dest_lng <= 180):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Destination coordinates out of range.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        algorithm = str(data.get("algorithm", "astar") or "astar").strip().lower()
        mode = str(data.get("mode", "walking") or "walking").strip().lower()

        if algorithm not in {"astar", "dijkstra"}:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_ALGORITHM",
                        "message": "algorithm must be 'astar' or 'dijkstra'.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = RoutingService().compute_route(
                source_lat=source_lat,
                source_lng=source_lng,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                mode=mode,
                algorithm=algorithm,
            )
        except Exception as exc:
            logger.exception("Route calculation failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ROUTING_INTERNAL_ERROR",
                        "message": "An internal routing error occurred.",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)

        error_code = result.get("error", {}).get("code", "ERROR")

        if error_code == "ROUTE_NOT_FOUND":
            http_status = status.HTTP_404_NOT_FOUND
        elif error_code == "GRAPH_NOT_LOADED":
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_400_BAD_REQUEST

        return Response(result, status=http_status)


class RerouteView(APIView):
    """POST /api/v1/routes/{route_id}/reroute - Compute a new route."""

    def post(self, request, route_id):
        data = request.data

        current_position = data.get("current_position") or {}
        destination = data.get("destination") or {}

        current_lat = current_position.get("lat")
        current_lng = current_position.get("lng")

        dest_lat = destination.get("lat")
        dest_lng = destination.get("lng")

        if current_lat is None or current_lng is None:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_CURRENT_POSITION",
                        "message": (
                            "current_position.lat and current_position.lng "
                            "are required."
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if dest_lat is None or dest_lng is None:
            dest_place_id = destination.get("place_id")

            if dest_place_id:
                from places.models import Place

                try:
                    place = Place.objects.get(id=dest_place_id)
                    dest_lat = place.lat
                    dest_lng = place.lng
                except Place.DoesNotExist:
                    return Response(
                        {
                            "success": False,
                            "error": {
                                "code": "PLACE_NOT_FOUND",
                                "message": (
                                    f"Place with id {dest_place_id} not found."
                                ),
                            },
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )

        if dest_lat is None or dest_lng is None:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_DESTINATION",
                        "message": "Destination coordinates are required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            current_lat = float(current_lat)
            current_lng = float(current_lng)
            dest_lat = float(dest_lat)
            dest_lng = float(dest_lng)
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

        if not (-90 <= current_lat <= 90) or not (-180 <= current_lng <= 180):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Current position is out of range.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (-90 <= dest_lat <= 90) or not (-180 <= dest_lng <= 180):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_COORDINATES",
                        "message": "Destination coordinates are out of range.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = data.get("reason", "traffic_change") or "traffic_change"

        try:
            result = RoutingService().reroute(
                route_id=route_id,
                current_lat=current_lat,
                current_lng=current_lng,
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                reason=reason,
            )
        except Exception as exc:
            logger.exception("Reroute calculation failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "REROUTE_INTERNAL_ERROR",
                        "message": "An internal rerouting error occurred.",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)

        error_code = result.get("error", {}).get("code", "REROUTE_FAILED")

        if error_code in {
            "ROUTE_NOT_FOUND",
            "SOURCE_UNREACHABLE",
            "DESTINATION_UNREACHABLE",
        }:
            http_status = status.HTTP_404_NOT_FOUND
        elif error_code == "GRAPH_NOT_LOADED":
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_400_BAD_REQUEST

        return Response(result, status=http_status)


class TrafficUpdateView(APIView):
    """POST /api/v1/traffic/update - Manual traffic simulation."""

    VALID_LEVELS = {
        "LOW",
        "MODERATE",
        "MEDIUM",
        "HIGH",
        "SEVERE",
        "CLOSED",
    }

    def post(self, request):
        edge_id = request.data.get("edge_id")
        traffic_level = str(
            request.data.get("traffic_level", "") or ""
        ).strip().upper()

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

        if traffic_level not in self.VALID_LEVELS:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_TRAFFIC_LEVEL",
                        "message": (
                            "traffic_level must be LOW, MODERATE, MEDIUM, "
                            "HIGH, SEVERE or CLOSED."
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from traffic.service import TrafficService

            result = TrafficService().apply_manual_traffic(
                edge_id=edge_id,
                traffic_level=traffic_level,
            )
        except Exception as exc:
            logger.exception("Manual traffic update failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "TRAFFIC_UPDATE_INTERNAL_ERROR",
                        "message": "Failed to update simulated traffic.",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)

        error = result.get("error", "Traffic update failed")
        return Response(
            {
                "success": False,
                "error": {
                    "code": "TRAFFIC_UPDATE_FAILED",
                    "message": str(error),
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
