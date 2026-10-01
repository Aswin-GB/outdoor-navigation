"""
URL routing for traffic telemetry API.
"""
from django.urls import path
from traffic.views import TelemetryView, TrafficStopView

urlpatterns = [
    path('location', TelemetryView.as_view(), name='telemetry-location'),
    path('stop', TrafficStopView.as_view(), name='telemetry-stop'),
]
