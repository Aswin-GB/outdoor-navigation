"""
Tests for API endpoints.
"""
import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        client = Client()
        response = client.get('/api/health')
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'database' in data
        assert 'graph_loaded' in data


@pytest.mark.django_db
class TestPlacesAPI:
    """Test places API."""

    def test_places_list(self):
        client = Client()
        response = client.get('/api/v1/places/')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'data' in data

    def test_places_search(self):
        client = Client()
        response = client.get('/api/v1/places/?q=library')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.django_db
class TestMapAPI:
    """Test map API."""

    def test_map_data(self):
        client = Client()
        response = client.get('/api/v1/map/')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'osm' in data['data']
        assert 'custom' in data['data']
        edges = data['data']['edges'].values()
        assert any(edge['from_name'] == '7 TH BLOCK' for edge in edges)
        assert any(
            edge['to_name'] == 'FE BLOCK / 11TH BLOCK'
            for edge in data['data']['edges'].values()
        )

    def test_map_version(self):
        client = Client()
        response = client.get('/api/v1/map/version')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'map_version' in data['data']


@pytest.mark.django_db
class TestRouteAPI:
    """Test routing API."""

    def test_route_missing_source(self):
        client = Client()
        response = client.post('/api/v1/routes', {
            'destination': {'lat': 9.57, 'lng': 77.68}
        }, content_type='application/json')
        assert response.status_code == 400

    def test_route_missing_destination(self):
        client = Client()
        response = client.post('/api/v1/routes', {
            'source': {'lat': 9.57, 'lng': 77.68}
        }, content_type='application/json')
        assert response.status_code == 400

    def test_route_invalid_coordinates(self):
        client = Client()
        response = client.post('/api/v1/routes', {
            'source': {'lat': 999, 'lng': 77.68},
            'destination': {'lat': 9.57, 'lng': 77.68}
        }, content_type='application/json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestTrafficAPI:
    """Test traffic API."""

    def test_traffic_list(self):
        client = Client()
        response = client.get('/api/v1/traffic/')
        assert response.status_code == 200

    def test_telemetry_missing_session(self):
        client = Client()
        response = client.post('/api/v1/telemetry/location', {
            'lat': 9.57,
            'lng': 77.68
        }, content_type='application/json')
        assert response.status_code == 400
