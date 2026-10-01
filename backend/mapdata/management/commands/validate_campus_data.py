"""
Django management command to validate campus data integrity.
"""
import json
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Validate campus data files (nodes, edges, places, geojson)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Campus Data Validation ==='))

        errors = []
        warnings = []

        # Validate nodes.json
        node_count = self._validate_nodes(errors, warnings)

        # Validate edges.json
        edge_count = self._validate_edges(errors, warnings)

        # Validate places.json
        place_count = self._validate_places(errors, warnings)

        # Validate campus.geojson
        geojson_valid = self._validate_geojson(errors, warnings)

        # Cross-validate references
        self._validate_references(errors, warnings)

        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== Summary ==='))
        self.stdout.write(f'Nodes: {node_count}')
        self.stdout.write(f'Edges: {edge_count}')
        self.stdout.write(f'Places: {place_count}')
        self.stdout.write(f'GeoJSON valid: {geojson_valid}')

        if warnings:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'Warnings ({len(warnings)}):'))
            for w in warnings:
                self.stdout.write(self.style.WARNING(f'  - {w}'))

        if errors:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f'Errors ({len(errors)}):'))
            for e in errors:
                self.stdout.write(self.style.ERROR(f'  - {e}'))
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('VALIDATION FAILED'))
            sys.exit(1)
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('VALIDATION PASSED'))

    def _validate_nodes(self, errors, warnings):
        """Validate nodes.json."""
        path = settings.NODES_JSON_PATH
        if not path.exists():
            errors.append(f'nodes.json not found: {path}')
            return 0

        with open(path) as f:
            data = json.load(f)

        nodes = data.get('nodes', [])
        node_ids = set()

        for node in nodes:
            nid = node.get('id')
            if not nid:
                errors.append('Node missing id')
                continue

            if nid in node_ids:
                errors.append(f'Duplicate node ID: {nid}')
            node_ids.add(nid)

            lat = node.get('lat')
            lng = node.get('lng')

            if lat is None or lng is None:
                errors.append(f'Node {nid} missing coordinates')
            elif not (-90 <= lat <= 90):
                errors.append(f'Node {nid} invalid latitude: {lat}')
            elif not (-180 <= lng <= 180):
                errors.append(f'Node {nid} invalid longitude: {lng}')

        # Check for disconnected components
        adjacency = {}
        for node in nodes:
            adjacency[node['id']] = [n['to'] for n in node.get('neighbors', [])]

        visited = set()
        components = 0

        for nid in adjacency:
            if nid not in visited:
                components += 1
                stack = [nid]
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        stack.extend(adjacency.get(current, []))

        if components > 1:
            warnings.append(f'Graph has {components} disconnected components')

        return len(nodes)

    def _validate_edges(self, errors, warnings):
        """Validate edges.json."""
        path = settings.EDGES_JSON_PATH
        if not path.exists():
            errors.append(f'edges.json not found: {path}')
            return 0

        with open(path) as f:
            data = json.load(f)

        edges = data.get('edges', [])
        edge_ids = set()

        for edge in edges:
            eid = edge.get('id')
            if not eid:
                errors.append('Edge missing id')
                continue

            if eid in edge_ids:
                errors.append(f'Duplicate edge ID: {eid}')
            edge_ids.add(eid)

            # Check required fields
            for field in ['from', 'to', 'distance_m', 'base_time_sec']:
                if field not in edge:
                    errors.append(f'Edge {eid} missing field: {field}')

            # Validate direction
            oneway = edge.get('oneway')
            if oneway is not None and not isinstance(oneway, bool):
                errors.append(f'Edge {eid} invalid oneway value: {oneway}')

            # Validate distance
            dist = edge.get('distance_m')
            if dist is not None and dist < 0:
                errors.append(f'Edge {eid} negative distance: {dist}')

        return len(edges)

    def _validate_places(self, errors, warnings):
        """Validate places.json."""
        path = settings.PLACES_JSON_PATH
        if not path.exists():
            errors.append(f'places.json not found: {path}')
            return 0

        with open(path) as f:
            data = json.load(f)

        places = data.get('places', [])
        place_ids = set()

        for place in places:
            pid = place.get('id')
            if not pid:
                errors.append('Place missing id')
                continue

            if pid in place_ids:
                errors.append(f'Duplicate place ID: {pid}')
            place_ids.add(pid)

            lat = place.get('lat')
            lng = place.get('lng')

            if lat is None or lng is None:
                errors.append(f'Place {pid} missing coordinates')
            elif not (-90 <= lat <= 90):
                errors.append(f'Place {pid} invalid latitude: {lat}')
            elif not (-180 <= lng <= 180):
                errors.append(f'Place {pid} invalid longitude: {lng}')

        return len(places)

    def _validate_geojson(self, errors, warnings):
        """Validate campus.geojson."""
        path = settings.CAMPUS_GEOJSON_PATH
        if not path.exists():
            errors.append(f'campus.geojson not found: {path}')
            return False

        with open(path) as f:
            data = json.load(f)

        if data.get('type') != 'FeatureCollection':
            errors.append('campus.geojson is not a FeatureCollection')
            return False

        features = data.get('features', [])
        if not features:
            errors.append('campus.geojson has no features')
            return False

        for feature in features:
            if 'geometry' not in feature:
                errors.append('Feature missing geometry')
                continue

            geom = feature['geometry']
            if 'type' not in geom:
                errors.append('Geometry missing type')
            if 'coordinates' not in geom:
                errors.append('Geometry missing coordinates')

        return len(errors) == 0

    def _validate_references(self, errors, warnings):
        """Cross-validate references between files."""
        # Load node IDs
        node_ids = set()
        try:
            with open(settings.NODES_JSON_PATH) as f:
                nodes_data = json.load(f)
            node_ids = {n['id'] for n in nodes_data.get('nodes', [])}
        except Exception:
            pass

        # Check edge references
        try:
            with open(settings.EDGES_JSON_PATH) as f:
                edges_data = json.load(f)
            for edge in edges_data.get('edges', []):
                from_node = edge.get('from')
                to_node = edge.get('to')
                if from_node and from_node not in node_ids:
                    errors.append(f"Edge {edge.get('id')} references unknown from_node: {from_node}")
                if to_node and to_node not in node_ids:
                    errors.append(f"Edge {edge.get('id')} references unknown to_node: {to_node}")
        except Exception:
            pass

        # Check place references
        try:
            with open(settings.PLACES_JSON_PATH) as f:
                places_data = json.load(f)
            for place in places_data.get('places', []):
                nearest = place.get('nearest_graph_node')
                if nearest and nearest not in node_ids:
                    warnings.append(f"Place {place.get('id')} references unknown graph node: {nearest}")
        except Exception:
            pass
