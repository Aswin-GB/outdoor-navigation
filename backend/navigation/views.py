"""
API views for navigation sessions.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from navigation.services import NavigationService


class NavigationStartView(APIView):
    """POST /api/v1/navigation/start - Start navigation session."""

    def post(self, request):
        data = request.data
        route_id = data.get('route_id')
        source = data.get('source', {})
        destination = data.get('destination', {})

        if not route_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_ROUTE',
                    'message': 'route_id is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        service = NavigationService()
        result = service.start_navigation(route_id, source, destination)

        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class NavigationLocationView(APIView):
    """POST /api/v1/navigation/location - Update navigation location."""

    def post(self, request):
        data = request.data
        navigation_id = data.get('navigation_id')
        lat = data.get('lat')
        lng = data.get('lng')
        edge_id = data.get('edge_id')

        if not navigation_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_NAVIGATION',
                    'message': 'navigation_id is required.',
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

        service = NavigationService()
        result = service.update_location(navigation_id, float(lat), float(lng), edge_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_404_NOT_FOUND)


class NavigationStopView(APIView):
    """POST /api/v1/navigation/stop - Stop navigation session."""

    def post(self, request):
        data = request.data
        navigation_id = data.get('navigation_id')

        if not navigation_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_NAVIGATION',
                    'message': 'navigation_id is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        service = NavigationService()
        result = service.stop_navigation(navigation_id)

        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
