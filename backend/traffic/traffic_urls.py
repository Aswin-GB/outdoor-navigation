"""URL routing for traffic API."""

from django.urls import path

from traffic.traffic_views import TrafficDetailView, TrafficListView
from traffic.views import TrafficSimulatorView

urlpatterns = [
    path(
        "simulate",
        TrafficSimulatorView.as_view(),
        name="traffic-simulate",
    ),
    path(
        "",
        TrafficListView.as_view(),
        name="traffic-list",
    ),
    path(
        "<str:edge_id>",
        TrafficDetailView.as_view(),
        name="traffic-detail",
    ),
]
