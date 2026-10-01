"""
Admin registration for places.
"""
from django.contrib import admin
from places.models import Place


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'lat', 'lng', 'is_active']
    list_filter = ['category', 'is_active', 'source']
    search_fields = ['name', 'description']
