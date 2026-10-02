# CampusFlow — Real-Time Dynamic Campus Navigation System

## Project Overview

CampusFlow is a production-oriented outdoor campus navigation platform built for the ReBuildX — Reverse · Rebuild · Reason hackathon challenge. It provides a Google-Maps-style user experience using OpenStreetMap-derived data, real-time crowd-based traffic analysis, and A* fastest-route calculation.

**Key Concept:** Static campus data + dynamic map data + custom graph + A* fastest routing + user-location crowd analysis + dynamic edge weights + dynamic rerouting + realtime WebSockets + Redis cache + trade-off analytics.

## Problem Statement

Campus navigation is typically static — it doesn't account for real-time conditions like crowd density, road closures, or temporary obstacles. CampusFlow solves this by:

1. Using real-time GPS telemetry from participating users to estimate crowd density on campus roads
2. Dynamically adjusting edge weights based on crowd analysis
3. Rerouting users when traffic conditions change significantly
4. Providing a trade-off dashboard to monitor system performance

## ReBuildX Context

Built for the **ReBuildX — Reverse · Rebuild · Reason** challenge, demonstrating:
- **Reverse:** Analyzing existing navigation systems and identifying gaps
- **Rebuild:** Creating a new system with real-time crowd intelligence
- **Reason:** Making data-driven decisions about routing and traffic management

## Core Concept

```
Static Campus Data (OSM)
        +
Dynamic Campus Map Data (Admin Editor)
        =
Current Campus Map
        +
Custom Graph (Nodes + Edges)
        +
A* Fastest Routing
        +
User-Location Crowd Analysis
        +
Dynamic Edge Weights
        +
Dynamic Rerouting
        +
Realtime WebSockets
        +
Redis Cache
        +
Trade-off Analytics
```

## Features

- **Interactive Campus Map** — MapLibre GL JS with OSM-derived data
- **Production Map Lifecycle** — MapLibre initializes once, creates empty GeoJSON sources immediately, and updates them when map data arrives without recreating the map instance
- **Dynamic Custom Map Data** — Admin editor for adding/editing campus features
- **Admin Graph Sync** — Feature creation/update/delete marks the routing graph stale and immediately reloads the in-memory graph so live route calculations reflect campus edits
- **Campus Places** — Searchable POIs with categories
- **Search** — Partial, case-insensitive place search
- **Current Location** — Browser Geolocation API with permission handling
- **Campus Graph** — In-memory graph with spatial index
- **A* Algorithm** — Real pathfinding with admissible heuristic
- **Fastest-Route Calculation** — Dynamic traffic-aware routing
- **ETA & Distance** — Real-time estimates based on current conditions
- **Crowd-Based Traffic** — GPS telemetry → map matching → crowd analysis
- **GPS Telemetry** — Server-validated location updates
- **Map Matching** — Spatial index-based edge matching
- **Active User Presence** — Redis TTL-based presence tracking
- **Configurable Crowd Thresholds** — LOW/MODERATE/HIGH/SEVERE levels
- **Dynamic Edge Weights** — Real-time travel time adjustments
- **Traffic Visualization** — Color-coded road segments
- **Route Impact Analyzer** — Smart rerouting decisions using actual route membership and ETA deltas
- **Mid-Journey Rerouting** — From current position, not origin, broadcast to WebSocket-connected navigation sessions
- **WebSocket** — Real-time navigation updates
- **Redis/Valkey State** — Caching and presence tracking
- **Route Cache** — Version-aware route caching
- **Map/Graph/Traffic Versions** — Cache invalidation support
- **Trade-off Dashboard** — Real system metrics
- **Traffic Demo Mode** — Live hackathon demonstration
- **Traffic Simulator Fallback** — SIMULATED data for testing and reset cleanup
- **Production Resilience** — Map data and places load independently so a places outage does not block campus map rendering
- **Admin Editing Workflow** — Edit existing features in-place, cancel/reset, and save changes without leaving the editor

## Architecture

```
                           USER
                            |
                     React Frontend
                            |
                    MapLibre GL JS
                            |
                    REST + WebSocket
                            |
                            v
                   Django + DRF/Channels
                            |
        +-------------------+--------------------+
        |                   |                    |
        v                   v                    v
   Map Service        Routing Engine       Traffic Engine
        |                   |                    |
        |                  A*                GPS telemetry
        |                   |                    |
        |              ETA calculation       Map matching
        |                   |                    |
        |               Rerouting             Crowd analysis
        |                   |                    |
        +-------------------+--------------------+
                            |
                 +----------+----------+
                 |                     |
                 v                     v
              SQLite               Redis/Valkey
          persistent data       realtime/cache state
                 |
                 v
           In-memory graph
           + spatial index
```

## Data Flow

### OSM Data Workflow
1. OSM data is downloaded for the campus area
2. `convert_osm.py` processes the OSM file
3. Generates `campus.geojson`, `nodes.json`, `edges.json`, `places.json`
4. Data is validated with `validate_campus_data`
5. Graph is loaded into memory at startup

### Dynamic Map Workflow
1. Admin adds feature via map editor
2. Feature stored in SQLite
3. Map version increments
4. Graph marked as stale
5. Route cache invalidated
6. Clients notified via WebSocket

### Traffic Analysis Flow
```
User GPS → Validate → Map Match → Edge ID → Redis Presence →
Active User Count → Traffic Classification → Dynamic Edge Weight →
Route Impact → Possible Reroute
```

## Map Editor

The admin map editor allows:
- Add roads, paths, pedestrian areas, buildings, parking, and landmarks
- Edit existing custom features in-place
- Delete features with soft-delete support
- Save changes and immediately reload the runtime graph for route calculations

**Operational Flow:**
1. Open the admin map editor
2. Add or update a routing-relevant feature
3. Save → map version increments, route cache invalidates, and graph reload is triggered
4. Runtime graph rebuilds in memory
5. New route requests immediately use the updated campus topology

**Backend sync behavior:**
- Admin writes persist to SQLite
- Routing-relevant changes mark the graph stale via `GraphManager.mark_stale()`
- The manager immediately reloads from the current campus graph data
- Route caches are cleared so clients do not reuse stale path results

## Graph Model

**NODE:**
- `id` — Unique identifier
- `lat`, `lng` — Coordinates

**EDGE:**
- `id` — Unique identifier
- `from`, `to` — Node references
- `distance_m` — Static distance
- `base_time_sec` — Static travel time
- `current_time_sec` — Dynamic travel time (A* uses this)
- `walkable` — Boolean
- `oneway` — Boolean
- `road_type` — Highway classification

## A* Algorithm

**Formula:** `f(n) = g(n) + h(n)`

- `g(n)` — Actual accumulated travel time
- `h(n)` — Estimated remaining travel time (haversine distance / max walking speed)

**Heuristic is admissible** — never overestimates actual travel time.

**Output:** route_id, path, coordinates, distance, ETA, algorithm, cache status, map version, traffic version

## Crowd Traffic Analyzer

**Reroute configuration:**
- `REROUTE_THRESHOLD_PERCENT` — 15%
- `MIN_REROUTE_INTERVAL_SECONDS` — 30 seconds
- `MAX_TRAFFIC_STALENESS_SECONDS` — 60 seconds

**Reroute logic:**
1. Check whether the affected edge is part of the active route
2. Read the current route context from the active navigation session
3. Compare the pre-change and post-change ETA for the impacted segment
4. Trigger `route_changed` only when the percentage threshold is crossed and the interval has elapsed
5. Broadcast the new route to the navigation WebSocket room

**Thresholds (prototype values):**
| Level | Active Users |
|-------|-------------|
| LOW | 0–3 |
| MODERATE | 4–7 |
| HIGH | 8–12 |
| SEVERE | 13+ |

**Congestion Formula:**
```
crowd_ratio = active_users / capacity
congestion_factor = 1.0 + (crowd_ratio × 2.0)
current_time = base_time × congestion_factor
```

## Map Matching

Uses a grid-based spatial index for O(1) candidate retrieval:
1. GPS point → nearby candidate roads (grid lookup)
2. Nearest valid edge (point-to-edge distance)
3. Match confidence based on distance

## Dynamic Edge Weights

- `base_time_sec` — Static, never overwritten
- `current_time_sec` — Dynamic, updated by traffic analyzer

**Example:**
- Base: 120 sec
- High crowd: 300 sec
- A* uses: 300 sec

## Rerouting

**Configuration:**
- `REROUTE_THRESHOLD_PERCENT` — 15%
- `MIN_REROUTE_INTERVAL_SECONDS` — 30 seconds
- `MAX_TRAFFIC_STALENESS_SECONDS` — 60 seconds

**Logic:**
1. Check if edge is part of active route
2. Check minimum reroute interval
3. Calculate ETA change percentage
4. Reroute only if threshold exceeded

## WebSockets

**Endpoint:** `/ws/navigation/{navigation_id}`

**Events:**
- `traffic_update` — Edge traffic state change
- `route_changed` — New route available
- `navigation_state` — Navigation status update
- `error` — Error notification

## Redis/Valkey Usage

1. Active user presence (`active_users:{edge_id}`)
2. Traffic state
3. Route cache (`route:{source}:{dest}:M{map}:T{traffic}`)
4. Temporary navigation state
5. Realtime event/channel coordination

## Route Cache

**Key format:** `route:{source_node}:{dest_node}:M{map_version}:T{traffic_version}`

**Invalidation:**
- Map version changes
- Traffic version changes
- TTL expiration

## Accuracy vs Computation Trade-off

**Trade-off Dashboard Metrics:**
- Traffic freshness
- Average A* latency
- Route response latency
- Total A* executions
- Cache hits/misses/hit rate
- Reroutes triggered
- Telemetry updates
- Active users
- WebSocket connections
- Current versions

**Controls:**
- Traffic update interval
- Traffic window
- Reroute threshold
- Minimum reroute interval
- Presence TTL

## Metrics

All metrics are **measured, not simulated**:
- A* execution count and latency
- Route API latency
- Cache hit rate
- Reroute count
- Telemetry processing time

## Privacy Model

- Traffic participation is **explicit** (opt-in)
- Temporary anonymous session IDs
- No personal identity required
- TTL-based presence (45 seconds)
- No raw GPS history persisted
- Location only shared during active navigation or explicit traffic contribution

## Security Model

- `DEBUG=False` in production
- `ALLOWED_HOSTS` configured
- CORS/CSRF origins restricted
- Secret key from environment
- Admin endpoints staff-protected
- Map feature mutation APIs authenticated
- All input validated server-side

## Project Structure

```
outdoor_navigation/
├── backend/
│   ├── config/           # Django settings, URLs, ASGI
│   ├── mapdata/          # CampusFeature model, map API
│   ├── places/           # Place model, search API
│   ├── routing_engine/   # Graph, A*, spatial index, service
│   ├── traffic/          # Presence, scoring, weights, analyzer
│   ├── navigation/       # Navigation session, WebSocket consumer
│   ├── analytics/        # Metrics tracking
│   ├── cache/            # Redis wrapper
│   ├── tests/            # Automated tests
│   ├── data/             # Campus data files
│   ├── manage.py
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── services/     # API clients
│   │   ├── utils/        # Utilities
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/           # Static assets
│   ├── package.json
│   └── vite.config.js
└── datasets/             # Original OSM-derived data
```

## API Documentation

### Health
- `GET /api/health` — System health check

### Map
- `GET /api/v1/map` — Get campus map data (OSM + custom)
- `GET /api/v1/map/version` — Get current map version
- `GET /api/v1/map/features` — List custom features
- `POST /api/v1/map/features` — Create feature (admin only)
- `PUT /api/v1/map/features/{id}` — Update feature (admin only)
- `DELETE /api/v1/map/features/{id}` — Delete feature (admin only)

### Places
- `GET /api/v1/places` — List/search places
- `GET /api/v1/places/{id}` — Get place details

### Routing
- `POST /api/v1/routes` — Compute fastest route
- `POST /api/v1/routes/{route_id}/reroute` — Reroute from current position

### Navigation
- `POST /api/v1/navigation/start` — Start navigation session
- `POST /api/v1/navigation/location` — Update location
- `POST /api/v1/navigation/stop` — Stop navigation

### Telemetry
- `POST /api/v1/telemetry/location` — Submit GPS telemetry
- `POST /api/v1/telemetry/stop` — Stop sharing location

### Traffic
- `GET /api/v1/traffic` — Get all traffic state
- `GET /api/v1/traffic/{edge_id}` — Get edge traffic state
- `POST /api/v1/traffic/simulate` — Simulate traffic (demo)

### Metrics
- `GET /api/v1/metrics` — Get system metrics

### WebSocket
- `WS /ws/navigation/{navigation_id}` — Real-time updates

## Environment Variables

### Backend
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=
CORS_ALLOWED_ORIGINS=
CSRF_TRUSTED_ORIGINS=
REDIS_URL=
SQLITE_PATH=
TRAFFIC_LOCATION_TTL_SECONDS=45
TRAFFIC_WINDOW_SECONDS=30
REROUTE_THRESHOLD_PERCENT=15
MIN_REROUTE_INTERVAL_SECONDS=30
MAX_TRAFFIC_STALENESS_SECONDS=60
```

### Frontend
```
VITE_API_BASE_URL=
VITE_WS_BASE_URL=
VITE_MAP_STYLE_URL=
```

## Local Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- uv (Python package manager)

### Backend Setup
```bash
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py import_places
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Production Build
```bash
# Backend
uv sync --frozen
uv run python manage.py collectstatic --no-input
uv run python manage.py migrate

# Frontend
npm run build
```

## uv Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init

# Add dependencies
uv add django djangorestframework channels uvicorn redis django-cors-headers

# Sync dependencies
uv sync

# Run commands
uv run python manage.py runserver
```

## SQLite Setup

**Development:** `./db.sqlite3` (default)

**Production (Render):** `/var/data/db.sqlite3` (requires persistent disk)

**Important:** Render's default filesystem is ephemeral. SQLite persistence requires a persistent disk.

## Render Deployment

### Frontend Deployment
1. Connect GitHub repository
2. Choose **Static Site**
3. Root directory: `frontend`
4. Build command: `npm install && npm run build`
5. Publish directory: `dist`
6. Environment variables:
   - `VITE_API_BASE_URL`
   - `VITE_WS_BASE_URL` (optional; when omitted, WebSockets use the API host and switch to `wss://` for HTTPS)
   - `VITE_MAP_STYLE_URL`

### Backend Deployment
1. Connect repository
2. Choose **Web Service**
3. Root directory: `backend`
4. Runtime: Python
5. Build command: `uv sync --frozen && uv run python manage.py collectstatic --no-input && uv run python manage.py migrate`
6. Start command: `uv run uvicorn config.asgi:application --host 0.0.0.0 --port $PORT`
7. Environment variables: (see Environment Variables section)
8. Browser GPS requires HTTPS and the user must allow the browser's location permission prompt. Set `VITE_API_BASE_URL` to this backend's HTTPS URL.

### Key Value Setup
1. Create Render Key Value service
2. Use internal connection URL for `REDIS_URL`
3. Without `REDIS_URL`, Channels and GPS presence use in-memory fallbacks suitable for a single backend process; configure Redis when running multiple processes or instances.

### Persistent Disk Setup
1. Attach persistent disk to backend service
2. Set `SQLITE_PATH=/var/data/db.sqlite3`
3. **Limitation:** Single instance only (SQLite constraint)

## Map Style Configuration

The map style is configurable via `VITE_MAP_STYLE_URL`.

**Default:** `https://demotiles.maplibre.org/style.json` (demo tiles)

**Production:** Use a permitted tile provider:
- OSM raster tiles (respect usage policy)
- MapTiler, Mapbox, or other commercial providers
- Self-hosted tiles

**Attribution:** Always display required attribution.

## OSM Attribution

- Data © OpenStreetMap contributors
- License: Open Database License (ODbL)
- Tile usage: Respect OSM tile usage policy
- Do not confuse OSM data with OSM tile infrastructure

## Testing

```bash
# Backend tests
cd backend
uv run python -m pytest tests/ -v

# Data validation
uv run python manage.py validate_campus_data

# Benchmark
uv run python manage.py benchmark_routing
```

## Benchmarking

```bash
uv run python manage.py benchmark_routing
```

Measures:
- Graph load time
- A* average/worst latency
- Route API latency
- Cache HIT/MISS latency

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis unavailable | System degrades gracefully; caching disabled |
| WebSocket fails | Auto-reconnect with backoff |
| GPS denied | Use traffic simulator fallback |
| No route found | Check graph connectivity |
| Map not loading | Verify VITE_MAP_STYLE_URL |

## Live Demo Instructions

1. Open campus map
2. Search destination
3. Request fastest route
4. Start navigation
5. Have friends open `/traffic-demo`
6. Friends grant location permission
7. Friends move onto the same road
8. Active user count increases
9. Traffic changes
10. Road visualization changes
11. Dynamic travel time changes
12. Current route is evaluated
13. Threshold is crossed
14. A* reruns from current position
15. New route sent through WebSocket
16. Frontend updates
17. Trade-off dashboard shows metrics

## Future Improvements

- Multi-campus support
- Indoor navigation (floor-aware)
- Public transit integration
- Machine learning for traffic prediction
- Mobile app (React Native)
- Offline map support
- Turn-by-turn voice navigation
# outdoor-navigation
