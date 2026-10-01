"""
URL routing for analytics API.
"""
from django.urls import path
from analytics.views import MetricsView

urlpatterns = [
    path('', MetricsView.as_view(), name='metrics'),
]
