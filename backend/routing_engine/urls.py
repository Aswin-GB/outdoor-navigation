"""
URL routing for routing engine API.
"""
from django.urls import path
from routing_engine.views import RouteView, RerouteView

urlpatterns = [
    path('routes', RouteView.as_view(), name='route'),
    path('routes/<str:route_id>/reroute', RerouteView.as_view(), name='reroute'),
]
