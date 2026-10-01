"""
URL routing for map data API.
"""
from django.urls import path
from mapdata.views import MapDataView, MapVersionView, FeatureListCreateView, FeatureDetailView

urlpatterns = [
    path('', MapDataView.as_view(), name='map-data'),
    path('version', MapVersionView.as_view(), name='map-version'),
    path('features', FeatureListCreateView.as_view(), name='feature-list-create'),
    path('features/<str:feature_id>', FeatureDetailView.as_view(), name='feature-detail'),
]
