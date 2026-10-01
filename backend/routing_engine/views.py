"""
API views for routing engine.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from routing_engine.service import RoutingService

logger = logging.getLogger('routing')


class RouteView(APIView):
    """POST /api/v1/routes - Compute fastest route."""

    def post(self, request):
        data = request.data

        # Validate source
        source = data.get('source', {})
        source_lat = source.get('lat')
        source_lng = source.get('lng')

        if source_lat is None or source_lng is None:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_SOURCE',
                    'message': 'Source coordinates are required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate destination
        destination = data.get('destination', {})
        dest_place_id = destination.get('place_id')
        dest_lat = destination.get('lat')
        dest_lng = destination.get('lng')

        if dest_place_id is None and (dest_lat is None or dest_lng is None):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_DESTINATION',
                    'message': 'Destination place_id or coordinates are required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Resolve place_id to coordinates if needed
        if dest_place_id and (dest_lat is None or dest_lng is None):
            from places.models import Place
            try:
                place = Place.objects.get(id=dest_place_id)
                dest_lat = place.lat
                dest_lng = place.lng
            except Place.DoesNotExist:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'PLACE_NOT_FOUND',
                        'message': f'Place with id {dest_place_id} not found.',
                    }
                }, status=status.HTTP_404_NOT_FOUND)

        # Validate coordinates
        try:
            source_lat = float(source_lat)
            source_lng = float(source_lng)
            dest_lat = float(dest_lat)
            dest_lng = float(dest_lng)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Coordinates must be valid numbers.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate coordinate ranges
        if not (-90 <= source_lat <= 90) or not (-180 <= source_lng <= 180):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Source coordinates out of range.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if not (-90 <= dest_lat <= 90) or not (-180 <= dest_lng <= 180):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Destination coordinates out of range.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        mode = data.get('mode', 'walking')

        service = RoutingService()
        result = service.compute_route(source_lat, source_lng, dest_lat, dest_lng, mode)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            error_code = result.get('error', {}).get('code', 'ERROR')
            if error_code == 'ROUTE_NOT_FOUND':
                http_status = status.HTTP_404_NOT_FOUND
            else:
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(result, status=http_status)


class RerouteView(APIView):
    """POST /api/v1/routes/{route_id}/reroute - Reroute from current position."""

    def post(self, request, route_id):
        data = request.data

        current = data.get('current_position', {})
        current_lat = current.get('lat')
        current_lng = current.get('lng')

        if current_lat is None or current_lng is None:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_POSITION',
                    'message': 'Current position coordinates are required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        destination = data.get('destination', {})
        dest_place_id = destination.get('place_id')
        dest_lat = destination.get('lat')
        dest_lng = destination.get('lng')

        if dest_place_id is None and (dest_lat is None or dest_lng is None):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_DESTINATION',
                    'message': 'Destination place_id or coordinates are required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Resolve place_id if needed
        if dest_place_id and (dest_lat is None or dest_lng is None):
            from places.models import Place
            try:
                place = Place.objects.get(id=dest_place_id)
                dest_lat = place.lat
                dest_lng = place.lng
            except Place.DoesNotExist:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'PLACE_NOT_FOUND',
                        'message': f'Place with id {dest_place_id} not found.',
                    }
                }, status=status.HTTP_404_NOT_FOUND)

        try:
            current_lat = float(current_lat)
            current_lng = float(current_lng)
            dest_lat = float(dest_lat)
            dest_lng = float(dest_lng)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_COORDINATES',
                    'message': 'Coordinates must be valid numbers.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        reason = data.get('reason', 'traffic_change')

        service = RoutingService()
        result = service.reroute(route_id, current_lat, current_lng, dest_lat, dest_lng, reason)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
