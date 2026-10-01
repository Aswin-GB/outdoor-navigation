"""
API views for traffic telemetry.
"""
import logging
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from traffic.service import TrafficService

logger = logging.getLogger('traffic')


class TelemetryView(APIView):
    """POST /api/v1/telemetry/location - Submit GPS telemetry."""

    def post(self, request):
        data = request.data

        session_id = data.get('session_id')
        lat = data.get('lat')
        lng = data.get('lng')
        timestamp = data.get('timestamp')

        if not session_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_SESSION',
                    'message': 'session_id is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if lat is None or lng is None:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'lat and lng are required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Coordinates must be valid numbers.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Coordinates out of range.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        service = TrafficService()
        result = service.process_telemetry(session_id, lat, lng, timestamp)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class TrafficStopView(APIView):
    """POST /api/v1/telemetry/stop - Stop sharing location."""

    def post(self, request):
        data = request.data
        session_id = data.get('session_id')

        if not session_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_SESSION',
                    'message': 'session_id is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        service = TrafficService()
        result = service.stop_sharing(session_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class TrafficSimulatorView(APIView):
    """POST /api/v1/traffic/simulate - Add/remove simulated users."""

    def post(self, request):
        data = request.data
        action = data.get('action')
        edge_id = data.get('edge_id')
        count = data.get('count', 1)

        if not edge_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_EDGE',
                    'message': 'edge_id is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        service = TrafficService()

        if action == 'add':
            result = service.add_simulated_users(edge_id, count)
        elif action == 'remove':
            result = service.remove_simulated_users(edge_id, count)
        elif action == 'reset':
            result = service.reset_simulation()
        else:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_ACTION',
                    'message': 'action must be add, remove, or reset.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
