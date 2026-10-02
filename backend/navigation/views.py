"""
API views for navigation sessions.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from navigation.services import NavigationService


class NavigationStartView(APIView):

    def post(self, request):
        data = request.data

        route_id = data.get("route_id")

        if not route_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_ROUTE",
                        "message": "route_id is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = NavigationService()

        result = service.start_navigation(
            route_id=route_id,
            source=data.get("source", {}),
            destination=data.get("destination", {}),
            route_nodes=data.get("route_nodes", []),
            route_edges=data.get("route_edges", []),
            duration_sec=data.get("duration_sec", 0),
        )

        return Response(
            result,
            status=(
                status.HTTP_201_CREATED
                if result["success"]
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class NavigationLocationView(APIView):

    def post(self, request):
        data = request.data

        navigation_id = data.get("navigation_id")
        lat = data.get("lat")
        lng = data.get("lng")
        edge_id = data.get("edge_id")
        current_eta_sec = data.get("current_eta_sec")

        if not navigation_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_NAVIGATION",
                        "message": "navigation_id is required.",
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

        result = NavigationService().update_location(
            navigation_id,
            float(lat),
            float(lng),
            edge_id,
            current_eta_sec,
        )

        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result["success"]
                else status.HTTP_404_NOT_FOUND
            ),
        )


class NavigationStopView(APIView):

    def post(self, request):
        navigation_id = request.data.get("navigation_id")

        if not navigation_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_NAVIGATION",
                        "message": "navigation_id is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = NavigationService().stop_navigation(
            navigation_id
        )

        return Response(
            result,
            status=(
                status.HTTP_200_OK
                if result["success"]
                else status.HTTP_404_NOT_FOUND
            ),
        )