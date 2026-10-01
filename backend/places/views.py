"""
API views for places.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from places.models import Place
from places.serializers import PlaceSerializer


class PlaceListView(APIView):
    """GET /api/v1/places - List/search places."""

    def get(self, request):
        queryset = Place.objects.filter(is_active=True)

        # Search by name (partial, case-insensitive)
        search = request.query_params.get('q', '')
        if search:
            queryset = queryset.filter(name__icontains=search)

        # Filter by category
        category = request.query_params.get('category', '')
        if category:
            queryset = queryset.filter(category__iexact=category)

        # Limit results
        limit = int(request.query_params.get('limit', 50))
        queryset = queryset[:limit]

        serializer = PlaceSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
            'count': len(serializer.data),
        })


class PlaceDetailView(APIView):
    """GET /api/v1/places/{id} - Get place details."""

    def get(self, request, place_id):
        try:
            place = Place.objects.get(id=place_id, is_active=True)
        except Place.DoesNotExist:
            return Response({
                'success': False,
                'error': {
                    'code': 'PLACE_NOT_FOUND',
                    'message': 'Place not found.',
                }
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = PlaceSerializer(place)
        return Response({
            'success': True,
            'data': serializer.data,
        })
