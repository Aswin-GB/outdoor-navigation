"""
Serializers for places.
"""
from rest_framework import serializers
from places.models import Place


class PlaceSerializer(serializers.ModelSerializer):
    """Serializer for Place."""

    class Meta:
        model = Place
        fields = [
            'id', 'name', 'lat', 'lng', 'category', 'source',
            'nearest_graph_node', 'description', 'is_active',
        ]
