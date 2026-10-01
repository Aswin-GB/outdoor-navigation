"""
URL routing for navigation API.
"""
from django.urls import path
from navigation.views import NavigationStartView, NavigationLocationView, NavigationStopView

urlpatterns = [
    path('start', NavigationStartView.as_view(), name='navigation-start'),
    path('location', NavigationLocationView.as_view(), name='navigation-location'),
    path('stop', NavigationStopView.as_view(), name='navigation-stop'),
]
