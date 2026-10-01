"""
Django management command to import places from JSON to database.
"""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from places.models import Place


class Command(BaseCommand):
    help = 'Import places from places.json into the database'

    def handle(self, *args, **options):
        self.stdout.write('Importing places...')

        path = settings.PLACES_JSON_PATH
        if not path.exists():
            self.stdout.write(self.style.ERROR(f'places.json not found: {path}'))
            return

        with open(path) as f:
            data = json.load(f)

        places = data.get('places', [])
        created = 0
        updated = 0

        for p in places:
            place, was_created = Place.objects.update_or_create(
                id=p['id'],
                defaults={
                    'name': p['name'],
                    'lat': p['lat'],
                    'lng': p['lng'],
                    'category': p.get('category', ''),
                    'source': p.get('source', 'osm'),
                    'osm_id': p.get('osm_id', ''),
                    'nearest_graph_node': p.get('nearest_graph_node', ''),
                    'nearest_graph_distance_m': p.get('nearest_graph_distance_m'),
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} new places, updated {updated} existing places'
        ))
