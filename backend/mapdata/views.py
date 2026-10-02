"""
API views for map data management.
"""

import json
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services import AnalyticsService
from mapdata.models import CampusFeature, MapVersion
from mapdata.serializers import CampusFeatureSerializer

logger = logging.getLogger("mapdata")


def _load_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _load_routing_edges():
    """Load generated edges and enrich them with endpoint geometry."""
    edges = {}
    nodes = {}

    try:
        if settings.NODES_JSON_PATH.exists():
            nodes_data = _load_json(settings.NODES_JSON_PATH)
            nodes = {
                node["id"]: node
                for node in nodes_data.get("nodes", [])
            }

        if not settings.EDGES_JSON_PATH.exists():
            return edges

        edges_data = _load_json(settings.EDGES_JSON_PATH)

        for edge in edges_data.get("edges", []):
            edge_id = edge.get("id")
            if not edge_id:
                continue

            from_node = nodes.get(edge.get("from"))
            to_node = nodes.get(edge.get("to"))

            geometry = None
            if from_node and to_node:
                geometry = {
                    "type": "LineString",
                    "coordinates": [
                        [from_node["lng"], from_node["lat"]],
                        [to_node["lng"], to_node["lat"]],
                    ],
                }

            edges[edge_id] = {
                "id": edge_id,
                "name": edge.get("name") or edge_id,
                "from": edge.get("from"),
                "to": edge.get("to"),
                "distance_m": edge.get("distance_m", 0),
                "base_time_sec": edge.get("base_time_sec", 0),
                "current_time_sec": edge.get(
                    "current_time_sec",
                    edge.get("base_time_sec", 0),
                ),
                "road_type": edge.get("road_type"),
                "oneway": edge.get("oneway", False),
                "traffic_level": edge.get("traffic_level", "LOW"),
                "source_way_id": edge.get("source_way_id"),
                "geometry": geometry,
            }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.exception("Failed to load generated routing edges: %s", exc)

    return edges


class MapDataView(APIView):
    """GET /api/v1/map/ - map GeoJSON, custom features and simulator edges."""

    def get(self, request):
        osm_data = None

        try:
            if settings.CAMPUS_GEOJSON_PATH.exists():
                osm_data = _load_json(settings.CAMPUS_GEOJSON_PATH)
        except (OSError, ValueError) as exc:
            logger.exception("Failed to load campus GeoJSON: %s", exc)

        custom_features = CampusFeature.objects.filter(is_active=True)
        custom_geojson = {
            "type": "FeatureCollection",
            "features": [feature.to_geojson() for feature in custom_features],
        }

        return Response({
            "success": True,
            "data": {
                "osm": osm_data,
                "custom": custom_geojson,
                "edges": _load_routing_edges(),
                "map_version": MapVersion.get_current_version(),
            },
        })


class MapVersionView(APIView):
    def get(self, request):
        return Response({
            "success": True,
            "data": {"map_version": MapVersion.get_current_version()},
        })


class FeatureListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    def get(self, request):
        features = CampusFeature.objects.filter(is_active=True)
        return Response({
            "success": True,
            "data": CampusFeatureSerializer(features, many=True).data,
        })

    def post(self, request):
        data = request.data
        feature_type = data.get("feature_type")
        geometry_data = data.get("geometry_data")

        if not feature_type or not geometry_data:
            return Response({
                "success": False,
                "error": {
                    "code": "INVALID_FEATURE",
                    "message": "feature_type and geometry_data are required.",
                },
            }, status=status.HTTP_400_BAD_REQUEST)

        if geometry_data.get("type") not in {"Point", "LineString", "Polygon"}:
            return Response({
                "success": False,
                "error": {
                    "code": "INVALID_GEOMETRY",
                    "message": "Geometry type must be Point, LineString, or Polygon.",
                },
            }, status=status.HTTP_400_BAD_REQUEST)

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
            reason=f"Added {feature_type}: {feature.name or 'unnamed'}"
        )

        if feature_type in {"road", "path", "pedestrian_area"}:
            from routing_engine.manager import get_graph_manager
            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

        AnalyticsService().record_map_edit()
        self._invalidate_route_cache()

        return Response({
            "success": True,
            "data": CampusFeatureSerializer(feature).data,
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def _invalidate_route_cache():
        try:
            from cache.redis import get_redis_client
            client = get_redis_client()
            if client:
                for key in client.keys("route:*"):
                    client.delete(key)
        except Exception:
            logger.exception("Route cache invalidation failed")


class FeatureDetailView(APIView):
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
            return Response({
                "success": False,
                "error": {
                    "code": "FEATURE_NOT_FOUND",
                    "message": "Feature not found.",
                },
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "data": CampusFeatureSerializer(feature).data,
        })

    def put(self, request, feature_id):
        feature = self.get_object(feature_id)
        if not feature:
            return Response({
                "success": False,
                "error": {
                    "code": "FEATURE_NOT_FOUND",
                    "message": "Feature not found.",
                },
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        changed_geometry = False

        if "name" in data:
            feature.name = data["name"]
        if "geometry_data" in data:
            feature.geometry_data = data["geometry_data"]
            changed_geometry = True
        if "properties" in data:
            feature.properties = data["properties"]
        if "is_active" in data:
            feature.is_active = data["is_active"]

        feature.version += 1
        feature.save()

        if feature.feature_type in {"road", "path", "pedestrian_area"} and changed_geometry:
            MapVersion.increment(
                reason=f"Updated {feature.feature_type}: {feature.name or 'unnamed'}"
            )
            FeatureListCreateView._invalidate_route_cache()

            from routing_engine.manager import get_graph_manager
            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

        AnalyticsService().record_map_edit()

        return Response({
            "success": True,
            "data": CampusFeatureSerializer(feature).data,
        })

    def delete(self, request, feature_id):
        feature = self.get_object(feature_id)
        if not feature:
            return Response({
                "success": False,
                "error": {
                    "code": "FEATURE_NOT_FOUND",
                    "message": "Feature not found.",
                },
            }, status=status.HTTP_404_NOT_FOUND)

        feature.is_active = False
        feature.save(update_fields=["is_active", "updated_at"])

        MapVersion.increment(
            reason=f"Deleted {feature.feature_type}: {feature.name or 'unnamed'}"
        )
        FeatureListCreateView._invalidate_route_cache()

        if feature.feature_type in {"road", "path", "pedestrian_area"}:
            from routing_engine.manager import get_graph_manager
            graph_manager = get_graph_manager()
            graph_manager.mark_stale()
            graph_manager.refresh_from_db()

        AnalyticsService().record_map_edit()

        return Response({
            "success": True,
            "data": {"id": str(feature.id), "deleted": True},
        })
