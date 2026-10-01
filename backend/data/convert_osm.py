from __future__ import annotations

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/mnt/data/map (1).osm')
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/mnt/data/campus_map_data')
OUT.mkdir(parents=True, exist_ok=True)

# For a campus outdoor navigation demo, prioritize pedestrian-accessible ways.
# Add more highway types here if you want vehicle routing too.
WALKABLE_HIGHWAYS = {
    'footway': 4.5,
    'path': 4.0,
    'pedestrian': 4.5,
    'living_street': 4.0,
    'service': 4.0,
    'residential': 4.5,
    'unclassified': 4.5,
    'tertiary': 5.0,
    'secondary': 5.0,
}

# Used only to draw / classify map features.
ROAD_LIKE = set(WALKABLE_HIGHWAYS) | {
    'primary', 'trunk', 'trunk_link', 'primary_link', 'secondary_link',
    'tertiary_link', 'motorway', 'motorway_link', 'track', 'cycleway',
}

def haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(x))

def polygon_centroid(coords):
    # Coordinates are (lat, lon). Simple mean is robust enough for small campus POIs.
    if not coords:
        return None
    return {
        'lat': sum(c[0] for c in coords) / len(coords),
        'lng': sum(c[1] for c in coords) / len(coords),
    }

def nearest_node(lat, lng, node_items):
    best = None
    best_d = float('inf')
    for nid, n in node_items:
        # Haversine is fine at campus scale; could be optimized with a spatial index later.
        d = haversine_m(lat, lng, n['lat'], n['lng'])
        if d < best_d:
            best_d, best = d, nid
    return best, round(best_d, 2)

root = ET.parse(INPUT).getroot()

nodes = {}
for n in root.findall('node'):
    nid = n.attrib['id']
    nodes[nid] = {
        'id': nid,
        'lat': float(n.attrib['lat']),
        'lng': float(n.attrib['lon']),
        'tags': {t.attrib['k']: t.attrib['v'] for t in n.findall('tag')},
    }

ways = []
for w in root.findall('way'):
    tags = {t.attrib['k']: t.attrib['v'] for t in w.findall('tag')}
    refs = [nd.attrib['ref'] for nd in w.findall('nd')]
    geom = [(nodes[r]['lat'], nodes[r]['lng']) for r in refs if r in nodes]
    if len(geom) >= 2:
        ways.append({
            'id': w.attrib['id'],
            'tags': tags,
            'refs': refs,
            'geom': geom,
        })

# -------------------------
# campus.geojson
# -------------------------
features = []
for w in ways:
    tags = dict(w['tags'])
    highway = tags.get('highway')
    building = tags.get('building')
    closed = len(w['refs']) >= 4 and w['refs'][0] == w['refs'][-1]

    if building or tags.get('landuse') or tags.get('leisure') or tags.get('amenity'):
        if closed:
            coords = [[lon, lat] for lat, lon in w['geom']]
            geometry = {'type': 'Polygon', 'coordinates': [coords]}
        else:
            coords = [[lon, lat] for lat, lon in w['geom']]
            geometry = {'type': 'LineString', 'coordinates': coords}
    else:
        coords = [[lon, lat] for lat, lon in w['geom']]
        geometry = {'type': 'LineString', 'coordinates': coords}

    props = {
        'osm_id': w['id'],
        'highway': highway,
        'name': tags.get('name'),
        'surface': tags.get('surface'),
        'building': building,
        'amenity': tags.get('amenity'),
        'leisure': tags.get('leisure'),
        'landuse': tags.get('landuse'),
    }
    # Keep original tags too, but under a compact object.
    props['osm_tags'] = tags

    features.append({
        'type': 'Feature',
        'id': w['id'],
        'geometry': geometry,
        'properties': props,
    })

# Include named nodes as point POIs.
for nid, n in nodes.items():
    if n['tags'].get('name'):
        features.append({
            'type': 'Feature',
            'id': nid,
            'geometry': {'type': 'Point', 'coordinates': [n['lng'], n['lat']]},
            'properties': {
                'osm_id': nid,
                'name': n['tags'].get('name'),
                'osm_tags': n['tags'],
            },
        })

campus_geojson = {
    'type': 'FeatureCollection',
    'name': 'college-campus',
    'features': features,
}
(OUT / 'campus.geojson').write_text(json.dumps(campus_geojson, indent=2), encoding='utf-8')

# -------------------------
# Graph nodes / edges
# -------------------------
# Only use navigation-friendly road/path ways by default.
graph_nodes = {}
edges = []
adj = defaultdict(list)

for w in ways:
    highway = w['tags'].get('highway')
    if highway not in WALKABLE_HIGHWAYS:
        continue

    # One graph node per OSM node on navigable ways. Shared OSM nodes naturally connect ways.
    valid_refs = [r for r in w['refs'] if r in nodes]
    for r in valid_refs:
        n = nodes[r]
        graph_nodes.setdefault(r, {'id': r, 'lat': n['lat'], 'lng': n['lng']})

    oneway = w['tags'].get('oneway') in {'yes', '1', 'true'}
    speed_kmh = WALKABLE_HIGHWAYS[highway]

    for a, b in zip(valid_refs, valid_refs[1:]):
        na, nb = nodes[a], nodes[b]
        d = haversine_m(na['lat'], na['lng'], nb['lat'], nb['lng'])
        if d <= 0:
            continue
        t = d / (speed_kmh * 1000 / 3600)
        edge_id = f"e_{w['id']}_{a}_{b}"
        edge = {
            'id': edge_id,
            'from': a,
            'to': b,
            'distance_m': round(d, 2),
            'base_time_sec': round(t, 2),
            'current_time_sec': round(t, 2),
            'road_type': highway,
            'speed_kmh': speed_kmh,
            'oneway': oneway,
            'traffic_level': 'LOW',
            'traffic_factor': 1.0,
            'source_way_id': w['id'],
            'name': w['tags'].get('name'),
        }
        edges.append(edge)
        adj[a].append({'edge_id': edge_id, 'to': b})
        if not oneway:
            reverse_id = f"e_{w['id']}_{b}_{a}"
            rev = dict(edge)
            rev['id'] = reverse_id
            rev['from'], rev['to'] = b, a
            edges.append(rev)
            adj[b].append({'edge_id': reverse_id, 'to': a})

# Attach adjacency to nodes for direct A* consumption if desired.
for nid in graph_nodes:
    graph_nodes[nid]['neighbors'] = adj.get(nid, [])

nodes_out = {
    'version': 1,
    'source': str(INPUT.name),
    'mode': 'walking',
    'nodes': list(graph_nodes.values()),
}
edges_out = {
    'version': 1,
    'source': str(INPUT.name),
    'mode': 'walking',
    'edges': edges,
}
(OUT / 'nodes.json').write_text(json.dumps(nodes_out, indent=2), encoding='utf-8')
(OUT / 'edges.json').write_text(json.dumps(edges_out, indent=2), encoding='utf-8')

# -------------------------
# Places / POIs
# -------------------------
places = []
graph_node_items = list(graph_nodes.items())
seen_names = set()

# Named node POIs
for nid, n in nodes.items():
    name = n['tags'].get('name')
    if not name:
        continue
    key = (name.strip().lower(), round(n['lat'], 5), round(n['lng'], 5))
    if key in seen_names:
        continue
    seen_names.add(key)
    near, near_d = nearest_node(n['lat'], n['lng'], graph_node_items) if graph_node_items else (None, None)
    places.append({
        'id': f'place_{nid}',
        'name': name,
        'lat': n['lat'],
        'lng': n['lng'],
        'category': n['tags'].get('amenity') or n['tags'].get('building') or n['tags'].get('tourism') or 'place',
        'source': 'osm_node',
        'osm_id': nid,
        'nearest_graph_node': near,
        'nearest_graph_distance_m': near_d,
    })

# Named way POIs / areas
for w in ways:
    name = w['tags'].get('name')
    if not name:
        continue
    c = polygon_centroid(w['geom'])
    if not c:
        continue
    key = (name.strip().lower(), round(c['lat'], 5), round(c['lng'], 5))
    if key in seen_names:
        continue
    seen_names.add(key)
    near, near_d = nearest_node(c['lat'], c['lng'], graph_node_items) if graph_node_items else (None, None)
    category = (
        w['tags'].get('amenity') or
        w['tags'].get('building') or
        w['tags'].get('leisure') or
        w['tags'].get('landuse') or
        w['tags'].get('highway') or
        'place'
    )
    places.append({
        'id': f"place_way_{w['id']}",
        'name': name,
        'lat': c['lat'],
        'lng': c['lng'],
        'category': category,
        'source': 'osm_way',
        'osm_id': w['id'],
        'nearest_graph_node': near,
        'nearest_graph_distance_m': near_d,
    })

places.sort(key=lambda x: x['name'].lower())
places_out = {
    'version': 1,
    'source': str(INPUT.name),
    'places': places,
}
(OUT / 'places.json').write_text(json.dumps(places_out, indent=2), encoding='utf-8')

summary = {
    'input': str(INPUT),
    'output': str(OUT),
    'osm_nodes': len(nodes),
    'osm_ways_with_geometry': len(ways),
    'geojson_features': len(features),
    'routing_nodes': len(graph_nodes),
    'routing_directed_edges': len(edges),
    'places': len(places),
    'walkable_highways': sorted(WALKABLE_HIGHWAYS),
}
(OUT / 'conversion_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
