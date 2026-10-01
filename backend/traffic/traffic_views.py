"""
API views for traffic state queries.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from traffic.service import TrafficService


class TrafficListView(APIView):
    """GET /api/v1/traffic - Get all traffic state."""

    def get(self, request):
        service = TrafficService()
        result = service.get_all_traffic()

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class TrafficDetailView(APIView):
    """GET /api/v1/traffic/{edge_id} - Get traffic state for an edge."""

    def get(self, request, edge_id):
        service = TrafficService()
        result = service.get_traffic_state(edge_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            error_code = result.get('error', '')
            if error_code == 'Edge not found':
                return Response(result, status=status.HTTP_404_NOT_FOUND)
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)
