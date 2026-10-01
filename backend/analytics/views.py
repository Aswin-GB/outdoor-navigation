"""
API views for analytics metrics.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from analytics.services import AnalyticsService


class MetricsView(APIView):
    """GET /api/v1/metrics - Get system metrics."""

    def get(self, request):
        service = AnalyticsService()
        metrics = service.get_metrics()
        return Response({
            'success': True,
            'data': metrics,
        }, status=status.HTTP_200_OK)
