"""
Serializers for map data.
"""
from rest_framework import serializers
from mapdata.models import CampusFeature, MapVersion


class CampusFeatureSerializer(serializers.ModelSerializer):
    """Serializer for CampusFeature."""

    class Meta:
        model = CampusFeature
        fields = [
            'id', 'feature_type', 'name', 'geometry_data', 'properties',
            'source', 'is_active', 'created_by', 'created_at', 'updated_at', 'version',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'version']


class MapVersionSerializer(serializers.ModelSerializer):
    """Serializer for MapVersion."""

    class Meta:
        model = MapVersion
        fields = ['version', 'created_at', 'reason']
