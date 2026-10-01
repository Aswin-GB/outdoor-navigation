"""
Place models for campus POIs.
"""
from django.db import models
import uuid


class Place(models.Model):
    """A searchable campus place/POI."""

    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    lat = models.FloatField()
    lng = models.FloatField()
    category = models.CharField(max_length=100, db_index=True, blank=True)
    source = models.CharField(max_length=50, default='osm')
    osm_id = models.CharField(max_length=255, blank=True)
    nearest_graph_node = models.CharField(max_length=255, blank=True)
    nearest_graph_distance_m = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'lat': self.lat,
            'lng': self.lng,
            'category': self.category,
            'source': self.source,
            'nearest_graph_node': self.nearest_graph_node,
        }
