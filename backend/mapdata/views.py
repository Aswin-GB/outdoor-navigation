"""
API views for map data management.
"""

import json
import logging

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services import AnalyticsService
from mapdata.models import CampusFeature, MapVersion
from mapdata.serializers import CampusFeatureSerializer
from routing_engine.manager import get_graph_manager

logger = logging.getLogger("mapdata")


class MapDataView(APIView):
    """GET /api/v1/map/ - Get map data plus routing edges for the simulator."""

    def get(self, request):
        from django.conf import settings

        osm_data = None

        try:
            with open(settings.CAMPUS_GEOJSON_PATH, encoding="utf-8") as file:
                osm_data = json.load(file)
        except FileNotFoundError:
            logger.warning(
                "Campus GeoJSON not found: %s",
                settings.CAMPUS_GEOJSON_PATH,
            )
        except json.JSONDecodeError as exc:
            logger.error(
                "Campus GeoJSON is invalid: %s",
                exc,
            )

        custom_features = CampusFeature.objects.filter(
            is_active=True
        )

        custom_geojson = {
            "type": "FeatureCollection",
            "features": [
                feature.to_geojson()
                for feature in custom_features
            ],
        }

        # The frontend traffic simulator needs to know which graph edges
        # are available. The previous implementation only returned OSM and
        # custom GeoJSON, leaving the Edge dropdown empty.
        edges = {}

        try:
            graph = get_graph_manager().get_graph()

            if graph:
                edges = {
                    edge_id: {
                        "id": edge_id,
                        "name": edge.get("name") or edge_id,
                        "from": edge.get("from"),
                        "to": edge.get("to"),
                        "distance_m": edge.get(
                            "distance_m",
                            0,
                        ),
                        "base_time_sec": edge.get(
                            "base_time_sec",
                            0,
                        ),
                        "current_time_sec": edge.get(
                            "current_time_sec",
                            edge.get(
                                "base_time_sec",
                                0,
                            ),
                        ),
                        "traffic_level": edge.get(
                            "traffic_level",
                            "LOW",
                        ),
                    }
                    for edge_id, edge in graph.edges.items()
                }

        except Exception as exc:
            logger.warning(
                "Failed to load routing edges for map response: %s",
                exc,
            )

        return Response(
            {
                "success": True,
                "data": {
                    "osm": osm_data,
                    "custom": custom_geojson,
                    "edges": edges,
                    "map_version": MapVersion.get_current_version(),
                },
            }
        )


class MapVersionView(APIView):
    """GET /api/v1/map/version - Get current map version."""

    def get(self, request):
        return Response(
            {
                "success": True,
                "data": {
                    "map_version": MapVersion.get_current_version(),
                },
            }
        )


class FeatureListCreateView(APIView):
    """GET/POST /api/v1/map/features - List or create features."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    def get(self, request):
        features = CampusFeature.objects.filter(is_active=True)
        serializer = CampusFeatureSerializer(features, many=True)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )

    def post(self, request):
        data = request.data

        feature_type = data.get("feature_type")
        geometry_data = data.get("geometry_data")

        if not feature_type:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_FEATURE",
                        "message": "feature_type is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not geometry_data:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_FEATURE",
                        "message": "geometry_data is required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_geometry_types = {
            "Point",
            "LineString",
            "Polygon",
        }

        geometry_type = geometry_data.get("type")

        if geometry_type not in valid_geometry_types:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_GEOMETRY",
                        "message": (
                            "Geometry type must be one of: "
                            "Point, LineString, Polygon."
                        ),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        feature = CampusFeature.objects.create(
            feature_type=feature_type,
            name=data.get("name", ""),
            geometry_data=geometry_data,
            properties=data.get("properties", {}),
            source=data.get("source", "admin"),
            created_by=(
                request.user.username
                if request.user.is_authenticated
                else "anonymous"
            ),
        )

        MapVersion.increment(
            reason=(
                f"Added {feature_type}: "
                f"{feature.name or 'unnamed'}"
            )
        )

        if feature_type in {
            "road",
            "path",
            "pedestrian_area",
        }:
            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

        AnalyticsService().record_map_edit()

        self._invalidate_route_cache()

        serializer = CampusFeatureSerializer(feature)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _invalidate_route_cache():
        try:
            from cache.redis import get_redis_client

            client = get_redis_client()
            if not client:
                return

            keys = client.keys("route:*")
            for key in keys:
                client.delete(key)

        except Exception:
            pass


class FeatureDetailView(APIView):
    """GET/PUT/DELETE /api/v1/map/features/{id}."""

    def get_permissions(self):
        if self.request.method in {"PUT", "DELETE"}:
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
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FEATURE_NOT_FOUND",
                        "message": "Feature not found.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CampusFeatureSerializer(feature)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )

    def put(self, request, feature_id):
        feature = self.get_object(feature_id)

        if not feature:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FEATURE_NOT_FOUND",
                        "message": "Feature not found.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data

        if "name" in data:
            feature.name = data["name"]

        if "geometry_data" in data:
            feature.geometry_data = data["geometry_data"]

        if "properties" in data:
            feature.properties = data["properties"]

        if "is_active" in data:
            feature.is_active = data["is_active"]

        feature.version += 1
        feature.save()

        if feature.feature_type in {
            "road",
            "path",
            "pedestrian_area",
        }:
            MapVersion.increment(
                reason=(
                    f"Updated {feature.feature_type}: "
                    f"{feature.name or 'unnamed'}"
                )
            )

            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

            FeatureListCreateView._invalidate_route_cache()

        AnalyticsService().record_map_edit()

        serializer = CampusFeatureSerializer(feature)

        return Response(
            {
                "success": True,
                "data": serializer.data,
            }
        )

    def delete(self, request, feature_id):
        feature = self.get_object(feature_id)

        if not feature:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FEATURE_NOT_FOUND",
                        "message": "Feature not found.",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        feature.is_active = False
        feature.save()

        MapVersion.increment(
            reason=(
                f"Deleted {feature.feature_type}: "
                f"{feature.name or 'unnamed'}"
            )
        )

        if feature.feature_type in {
            "road",
            "path",
            "pedestrian_area",
        }:
            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

        FeatureListCreateView._invalidate_route_cache()
        AnalyticsService().record_map_edit()

        return Response(
            {
                "success": True,
                "data": {
                    "id": str(feature.id),
                    "deleted": True,
                },
            }
        )
