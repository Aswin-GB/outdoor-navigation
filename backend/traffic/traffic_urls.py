"""
URL routing for traffic API.
"""
from django.urls import path
from traffic.views import TrafficSimulatorView
from traffic.traffic_views import TrafficListView, TrafficDetailView

urlpatterns = [
    path('', TrafficListView.as_view(), name='traffic-list'),
    path('<str:edge_id>', TrafficDetailView.as_view(), name='traffic-detail'),
    path('simulate', TrafficSimulatorView.as_view(), name='traffic-simulate'),
]
