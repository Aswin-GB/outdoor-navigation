"""
URL configuration for CampusFlow backend.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint."""
    from django.db import connection
    from cache.redis import get_redis_client
    from routing_engine.manager import GraphManager

    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            db_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        client = get_redis_client()
        if client:
            client.ping()
            redis_ok = True
    except Exception:
        pass

    graph_loaded = False
    graph_version = 0
    try:
        gm = GraphManager()
        graph = gm.get_graph()
        if graph:
            graph_loaded = True
            graph_version = gm.get_graph_version()
    except Exception:
        pass

    from mapdata.models import MapVersion
    try:
        mv = MapVersion.objects.first()
        map_version = mv.version if mv else 0
    except Exception:
        map_version = 0

    from traffic.service import TrafficService
    try:
        ts = TrafficService()
        traffic_version = ts.get_traffic_version()
    except Exception:
        traffic_version = 0

    status = 'ok' if (db_ok and graph_loaded) else 'degraded'

    return JsonResponse({
        'status': status,
        'database': db_ok,
        'redis': redis_ok,
        'graph_loaded': graph_loaded,
        'graph_version': graph_version,
        'map_version': map_version,
        'traffic_version': traffic_version,
    })


def api_root(request):
    """API root endpoint."""
    return JsonResponse({
        'name': 'CampusFlow API',
        'version': '1.0.0',
        'endpoints': {
            'map': '/api/v1/map/',
            'places': '/api/v1/places/',
            'routes': '/api/v1/routes/',
            'navigation': '/api/v1/navigation/',
            'telemetry': '/api/v1/telemetry/',
            'traffic': '/api/v1/traffic/',
            'metrics': '/api/v1/metrics/',
            'health': '/api/health/',
        }
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health', health_check, name='health'),
    path('api/', api_root, name='api-root'),
    path('api/v1/map/', include('mapdata.urls')),
    path('api/v1/places/', include('places.urls')),
    path('api/v1/', include('routing_engine.urls')),
    path('api/v1/navigation/', include('navigation.urls')),
    path('api/v1/telemetry/', include('traffic.urls')),
    path('api/v1/traffic/', include('traffic.traffic_urls')),
    path('api/v1/metrics/', include('analytics.urls')),
]
