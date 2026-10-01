"""
Map data models for dynamic campus features and versioning.
"""
from django.db import models
import json
import uuid


class CampusFeature(models.Model):
    """Custom campus features added by admin users."""

    class FeatureType(models.TextChoices):
        ROAD = 'road', 'Road'
        PATH = 'path', 'Path'
        PEDESTRIAN_AREA = 'pedestrian_area', 'Pedestrian Area'
        BUILDING = 'building', 'Building'
        GATE = 'gate', 'Gate'
        PARKING = 'parking', 'Parking'
        LANDMARK = 'landmark', 'Landmark'
        FACILITY = 'facility', 'Facility'
        OTHER = 'other', 'Other'

    class Source(models.TextChoices):
        OSM = 'osm', 'OpenStreetMap'
        ADMIN = 'admin', 'Admin Editor'
        SURVEY = 'survey', 'Campus Survey'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feature_type = models.CharField(max_length=20, choices=FeatureType.choices)
    name = models.CharField(max_length=255, blank=True)
    geometry_data = models.JSONField()  # GeoJSON geometry
    properties = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ADMIN)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.feature_type}: {self.name or 'Unnamed'}"

    def to_geojson(self):
        """Convert to GeoJSON feature."""
        return {
            'type': 'Feature',
            'id': str(self.id),
            'geometry': self.geometry_data,
            'properties': {
                'id': str(self.id),
                'feature_type': self.feature_type,
                'name': self.name,
                'source': self.source,
                'is_active': self.is_active,
                **self.properties,
            }
        }


class MapVersion(models.Model):
    """Tracks map version for cache invalidation."""

    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f"Map Version {self.version}"

    @classmethod
    def get_current_version(cls) -> int:
        """Get the current map version."""
        latest = cls.objects.first()
        return latest.version if latest else 0

    @classmethod
    def increment(cls, reason: str = '') -> 'MapVersion':
        """Increment the map version."""
        current = cls.get_current_version()
        return cls.objects.create(version=current + 1, reason=reason)
