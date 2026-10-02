# CampusFlow — Real-Time Campus Navigation

CampusFlow is a web-based campus navigation prototype. It combines an
interactive campus map, walking routes, browser location sharing, traffic
simulation, and live navigation updates.

## Features

- **Campus map:** MapLibre GL JS with satellite imagery, campus features, and
  searchable place markers.
- **Route planner:** Choose campus buildings or places as endpoints and request
  a walking route using A* (fastest) or Dijkstra (shortest). The route response
  includes its path, distance, estimated duration, algorithm, and cache/version
  information.
- **Navigation:** Start and stop a navigation session, share browser location
  while navigating, and receive live updates over WebSockets.
- **Traffic panel and demo:** View current edge traffic; opt in to sharing
  location in the demo, add or remove simulated users, set a manual traffic
  level, and reset simulated traffic.
- **Traffic-aware routing:** GPS reports are matched to nearby graph edges.
  Traffic changes update edge travel times and can trigger a reroute when the
  configured threshold is exceeded.
- **Map editor:** View and manage custom campus map features. Map-feature write
  endpoints require an authenticated administrator.
- **Metrics:** Inspect backend analytics such as route, cache, traffic, and
  telemetry metrics.
- **Fallback storage:** SQLite is used for persistent application data.
  Redis/Valkey is optional; in-memory fallbacks are available for single-process
  development.

## Architecture

```text
React + Vite
  ├── MapLibre map and campus UI
  ├── REST API requests
  └── Navigation WebSocket
          │
          ▼
Django + Django REST Framework + Django Channels
  ├── Places and map data
  ├── Routing engine (A*, Dijkstra, graph and spatial index)
  ├── Traffic and navigation services
  └── Analytics
          │
          ├── SQLite (application data)
          └── Redis/Valkey (optional cache, presence and channel layer)
```

## Repository Layout

```text
.
├── backend/
│   ├── analytics/       # Metrics API and services
│   ├── cache/           # Optional Redis integration
│   ├── config/          # Django settings, HTTP and ASGI routing
│   ├── data/            # Campus GeoJSON, graph and place data
│   ├── mapdata/         # Campus map API, editor data and commands
│   ├── navigation/      # Navigation sessions and WebSocket consumer
│   ├── places/          # Place API and database model
│   ├── routing_engine/  # Graph, A*, Dijkstra, route and reroute APIs
│   ├── tests/           # Backend tests
│   ├── traffic/         # Telemetry, traffic scoring and simulation
│   ├── build.sh         # Backend deployment/build helper
│   ├── manage.py
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── components/  # Map, route, navigation, traffic and editor UI
    │   ├── hooks/       # Data, location, navigation and traffic hooks
    │   └── services/    # REST and WebSocket clients
    ├── package.json
    └── vite.config.js
```

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Optional: Redis or Valkey for shared cache, presence, and multi-process
  WebSocket support

The current campus data files are in `backend/data/`: `campus.geojson`,
`nodes.json`, `edges.json`, and `places.json`.

## Run Locally

Start the backend first. In a terminal:

```bash
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py import_places
uv run python manage.py runserver 0.0.0.0:8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The frontend uses `http://localhost:8000` as its
default API and WebSocket host. Configure `VITE_API_BASE_URL` or
`VITE_WS_BASE_URL` when the backend is hosted elsewhere.

To create an administrator for the protected Django admin and map-feature write
APIs, run this from `backend/`:

```bash
uv run python manage.py createsuperuser
```

### Optional: regenerate campus data

`backend/data/convert_osm.py` converts an OSM XML extract into the campus
GeoJSON and graph/place JSON files. Provide the input extract and output
directory explicitly:

```bash
cd backend
uv run python data/convert_osm.py path/to/campus.osm data
```

Review the generated files before replacing the current campus data.

## Configuration

Set environment variables in the process environment before starting the
backend or frontend. The application does not load a `.env` file itself.

### Backend

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django secret key; set a private value when deploying | Development-only fallback |
| `DJANGO_DEBUG` | Enable Django debug mode (`true`, `1`, or `yes`) | `False` |
| `DJANGO_ALLOWED_HOSTS` | Allowed host names; comma-separated or a JSON array | Localhost and configured CampusFlow hosts |
| `CORS_ALLOWED_ORIGINS` | Browser origins allowed to call the API | Local Vite origins and configured CampusFlow hosts |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for Django CSRF checks | Local Vite origins and configured CampusFlow hosts |
| `SQLITE_PATH` | SQLite database file path | `backend/db.sqlite3` |
| `REDIS_URL` | Optional Redis/Valkey connection URL | Unset; in-memory channel/presence fallbacks |
| `TRAFFIC_LOCATION_TTL_SECONDS` | How long a reported location contributes to presence | `45` |
| `TRAFFIC_WINDOW_SECONDS` | Traffic analysis window | `30` |
| `REROUTE_THRESHOLD_PERCENT` | ETA-change percentage needed to consider a reroute | `15` |
| `MIN_REROUTE_INTERVAL_SECONDS` | Minimum interval between reroutes | `30` |
| `MAX_TRAFFIC_STALENESS_SECONDS` | Maximum traffic-data age used for rerouting | `60` |

The prototype traffic levels are LOW (0–3 active users), MODERATE (4–7), HIGH
(8–12), and SEVERE (13 or more).

### Frontend

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Backend HTTP API base URL | `http://localhost:8000` |
| `VITE_WS_BASE_URL` | WebSocket base URL; falls back to `VITE_API_BASE_URL` | Derived from the API URL |
| `VITE_MAP_STYLE_URL` | Style URL accepted by the reusable `BaseMap` component | MapLibre demo style |

The main campus view currently defines its satellite imagery style in
`CampusMap`; `VITE_MAP_STYLE_URL` applies to the reusable `BaseMap` component.
Map data and tile imagery are separate sources. Keep the displayed attribution
and comply with the selected tile provider's terms.

## API Overview

The API returns JSON. Common endpoints include:

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Database, graph, Redis, map-version, and traffic-version status |
| `GET` | `/api/` | API name, version, and endpoint index |
| `GET` | `/api/v1/map/` | Campus GeoJSON, custom features, and routing edges |
| `GET` | `/api/v1/map/version` | Current map version |
| `GET` | `/api/v1/map/features` | List custom map features |
| `POST` | `/api/v1/map/features` | Create a custom map feature (administrator only) |
| `GET`, `PUT`, `DELETE` | `/api/v1/map/features/{id}` | Read or manage a custom feature; writes require an administrator |
| `GET` | `/api/v1/places/` | Search/list campus places |
| `GET` | `/api/v1/places/{place_id}` | Retrieve a place |
| `POST` | `/api/v1/routes` | Compute a route |
| `POST` | `/api/v1/routes/{route_id}/reroute` | Recalculate a route from a current position |
| `POST` | `/api/v1/traffic/update` | Set a manual traffic level for an edge |
| `GET` | `/api/v1/traffic/` | Get current traffic state |
| `GET` | `/api/v1/traffic/{edge_id}` | Get state for one edge |
| `POST` | `/api/v1/traffic/simulate` | Add/remove simulated users or reset the simulation |
| `POST` | `/api/v1/telemetry/location` | Submit an opt-in GPS traffic update |
| `POST` | `/api/v1/telemetry/stop` | Stop sharing a traffic session |
| `POST` | `/api/v1/navigation/start` | Start a navigation session |
| `POST` | `/api/v1/navigation/location` | Update a navigation session's location |
| `POST` | `/api/v1/navigation/stop` | Stop a navigation session |
| `GET` | `/api/v1/metrics/` | Read system metrics |
| `WS` | `/ws/navigation/{navigation_id}/` | Receive navigation and reroute events |

Example route request:

```json
{
  "source": { "lat": 9.5738, "lng": 77.6739 },
  "destination": { "place_id": "place_12238903087" },
  "mode": "walking",
  "algorithm": "astar"
}
```

Set `algorithm` to `astar` or `dijkstra`. The route response includes the
geographic path, graph node/edge paths, distance, estimated duration, and
map/traffic versions. The WebSocket sends events such as
`connection_established`, `traffic_update`, `route_changed`,
`navigation_state`, and `error`.

## Data and Traffic Flow

1. Campus map and graph data are read from `backend/data/`.
2. Place records are imported into SQLite with `import_places`.
3. Route requests match their endpoints to the in-memory campus graph and run
   the selected routing algorithm using current edge travel times.
4. When location sharing is enabled, GPS updates are validated and matched to
   nearby graph edges.
5. Active-user presence contributes to traffic classification and dynamic edge
   travel times. Traffic changes can trigger rerouting for active navigation
   sessions and are sent over WebSockets.
6. Map edits are stored as custom features and can update the routing graph
   when they affect roads or paths.

Redis/Valkey is recommended when running multiple backend workers or instances.
Without it, in-memory fallbacks are intended for local or single-process use.

## Validation and Tests

Run from `backend/`:

```bash
# Backend test suite
uv run python -m pytest tests/ -v

# Validate the campus map and routing data
uv run python manage.py validate_campus_data

# Benchmark graph loading and routing
uv run python manage.py benchmark_routing
```

Build the frontend from `frontend/`:

```bash
npm run build
```

## Deployment

### Frontend

Deploy `frontend` as a static site:

```bash
npm ci
npm run build
```

Publish the generated `frontend/dist` directory. Set `VITE_API_BASE_URL` to the
deployed backend URL. Set `VITE_WS_BASE_URL` only if WebSockets use a different
host; HTTPS pages automatically use secure `wss://` connections.

### Backend

`backend/build.sh` syncs Python dependencies, collects static files, applies
migrations, imports campus places, and runs Django's non-interactive
`createsuperuser` command. Configure the Django superuser environment variables
required by that command before using the script in a deployment build. Start
the ASGI app with an ASGI server, for example:

```bash
cd backend
uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

Set a private `DJANGO_SECRET_KEY`, production `DJANGO_ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS`. Use HTTPS for browser
geolocation. A persistent disk is required if SQLite data must survive
redeployments; SQLite is intended for a single backend instance.

## Attribution

Campus map data is derived from © OpenStreetMap contributors and is licensed
under the Open Database License (ODbL). Satellite imagery is provided separately
from the map data; follow the imagery provider's attribution and usage
requirements.
