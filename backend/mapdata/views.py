"""
API views for map data management.
"""
import json
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from mapdata.models import CampusFeature, MapVersion
from mapdata.serializers import CampusFeatureSerializer, MapVersionSerializer
from routing_engine.manager import get_graph_manager
from analytics.services import AnalyticsService

logger = logging.getLogger('mapdata')


class MapDataView(APIView):
    """GET /api/v1/map - Get campus map data (OSM + custom features)."""

    def get(self, request):
        from django.conf import settings

        # Load OSM GeoJSON
        osm_data = None
        try:
            with open(settings.CAMPUS_GEOJSON_PATH) as f:
                osm_data = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Campus GeoJSON not found: {settings.CAMPUS_GEOJSON_PATH}")

        # Load custom features
        custom_features = CampusFeature.objects.filter(is_active=True)
        custom_geojson = {
            'type': 'FeatureCollection',
            'features': [f.to_geojson() for f in custom_features],
        }

        # Get current map version
        map_version = MapVersion.get_current_version()

        return Response({
            'success': True,
            'data': {
                'osm': osm_data,
                'custom': custom_geojson,
                'map_version': map_version,
            }
        })


class MapVersionView(APIView):
    """GET /api/v1/map/version - Get current map version."""

    def get(self, request):
        version = MapVersion.get_current_version()
        return Response({
            'success': True,
            'data': {
                'map_version': version,
            }
        })


class FeatureListCreateView(APIView):
    """GET/POST /api/v1/map/features - List or create features."""

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    def get(self, request):
        features = CampusFeature.objects.filter(is_active=True)
        serializer = CampusFeatureSerializer(features, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def post(self, request):
        data = request.data

        # Validate required fields
        feature_type = data.get('feature_type')
        geometry_data = data.get('geometry_data')

        if not feature_type:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_FEATURE',
                    'message': 'feature_type is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        if not geometry_data:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_FEATURE',
                    'message': 'geometry_data is required.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate geometry type
        valid_types = ['Point', 'LineString', 'Polygon']
        geom_type = geometry_data.get('type')
        if geom_type not in valid_types:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_GEOMETRY',
                    'message': f'Geometry type must be one of: {", ".join(valid_types)}.',
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create feature
        feature = CampusFeature.objects.create(
            feature_type=feature_type,
            name=data.get('name', ''),
            geometry_data=geometry_data,
            properties=data.get('properties', {}),
            source=data.get('source', 'admin'),
            created_by=request.user.username if request.user.is_authenticated else 'anonymous',
        )

        # Increment map version
        MapVersion.increment(reason=f"Added {feature_type}: {feature.name or 'unnamed'}")

        # Mark graph as stale if routing-relevant and trigger immediate reload
        if feature_type in ['road', 'path', 'pedestrian_area']:
            gm = get_graph_manager()
            gm.mark_stale()
            gm.refresh_from_db()

        # Record analytics
        AnalyticsService().record_map_edit()

        # Invalidate route cache
        try:
            from cache.redis import get_redis_client
            client = get_redis_client()
            if client:
                keys = client.keys("route:*")
                for key in keys:
                    client.delete(key)
        except Exception:
            pass

        serializer = CampusFeatureSerializer(feature)
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_201_CREATED)


class FeatureDetailView(APIView):
    """GET/PUT/DELETE /api/v1/map/features/{id} - Feature detail operations."""

    def get_permissions(self):
        if self.request.method in ['PUT', 'DELETE']:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    def get_object(self, feature_id):
        try:
            return CampusFeature.objects.get(id=feature_id)
        except CampusFeature.DoesNotExist:
            return None

    def get(self, request, feature_id):
        feature = self.get_object(feature_id)
        if not feature:
            return Response({
                'success': False,
                'error': {
                    'code': 'FEATURE_NOT_FOUND',
                    'message': 'Feature not found.',
                }
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = CampusFeatureSerializer(feature)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def put(self, request, feature_id):
        feature = self.get_object(feature_id)
        if not feature:
            return Response({
                'success': False,
                'error': {
                    'code': 'FEATURE_NOT_FOUND',
                    'message': 'Feature not found.',
                }
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        # Update fields
        if 'name' in data:
            feature.name = data['name']
        if 'geometry_data' in data:
            feature.geometry_data = data['geometry_data']
        if 'properties' in data:
            feature.properties = data['properties']
        if 'is_active' in data:
            feature.is_active = data['is_active']

        feature.version += 1
        feature.save()

        # Increment map version if routing-relevant
        if feature.feature_type in ['road', 'path', 'pedestrian_area']:
            MapVersion.increment(reason=f"Updated {feature.feature_type}: {feature.name or 'unnamed'}")
            gm = get_graph_manager()
            gm.mark_stale()
            gm.refresh_from_db()

            # Invalidate route cache
            try:
                from cache.redis import get_redis_client
                client = get_redis_client()
                if client:
                    keys = client.keys("route:*")
                    for key in keys:
                        client.delete(key)
            except Exception:
                pass

        AnalyticsService().record_map_edit()

        serializer = CampusFeatureSerializer(feature)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def delete(self, request, feature_id):
        feature = self.get_object(feature_id)
        if not feature:
            return Response({
                'success': False,
                'error': {
                    'code': 'FEATURE_NOT_FOUND',
                    'message': 'Feature not found.',
                }
            }, status=status.HTTP_404_NOT_FOUND)

        # Soft delete
        feature.is_active = False
        feature.save()

        # Increment map version
        MapVersion.increment(reason=f"Deleted {feature.feature_type}: {feature.name or 'unnamed'}")

        # Mark graph as stale if routing-relevant
        if feature.feature_type in ['road', 'path', 'pedestrian_area']:
            gm = get_graph_manager()
            gm.mark_stale()
            gm.refresh_from_db()

        # Invalidate route cache
        try:
            from cache.redis import get_redis_client
            client = get_redis_client()
            if client:
                keys = client.keys("route:*")
                for key in keys:
                    client.delete(key)
        except Exception:
            pass

        AnalyticsService().record_map_edit()

        return Response({
            'success': True,
            'data': {'id': str(feature.id), 'deleted': True},
        })
