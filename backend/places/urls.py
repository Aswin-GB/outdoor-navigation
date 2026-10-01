"""
URL routing for places API.
"""
from django.urls import path
from places.views import PlaceListView, PlaceDetailView

urlpatterns = [
    path('', PlaceListView.as_view(), name='place-list'),
    path('<str:place_id>', PlaceDetailView.as_view(), name='place-detail'),
]
