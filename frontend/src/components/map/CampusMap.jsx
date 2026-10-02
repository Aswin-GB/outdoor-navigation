/**
 * Main campus map component using MapLibre GL JS.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { apiPost } from '../../services/api'

const MAP_STYLE = import.meta.env.VITE_MAP_STYLE_URL || 'https://demotiles.maplibre.org/style.json'

const SATELLITE_STYLE = {
  version: 8,
  sources: {
    'satellite-tiles': {
      type: 'raster',
      tiles: ['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, iBird, USDA, USGS, ASTER, NASA, GeoScience Australia, and others',
    },
  },
  layers: [
    {
      id: 'satellite',
      type: 'raster',
      source: 'satellite-tiles',
    },
  ],
}

// Campus center (from actual campus data)
const CAMPUS_CENTER = [77.68, 9.57]
const DEFAULT_ZOOM = 15

// Traffic level colors
const TRAFFIC_COLORS = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  SEVERE: '#ef4444',
}

export default function CampusMap({
  mapData,
  places = [],
  route = null,
  trafficData = null,
  selectedPlace = null,
  onPlaceSelect,
  loading = false,
}) {
  const mapContainer = useRef(null)
  const map = useRef(null)
  const markersRef = useRef([])
  const [mapLoaded, setMapLoaded] = useState(false)
  const [activePopup, setActivePopup] = useState(null)
  const [basemap, setBasemap] = useState('satellite')

  // Routing State
  const [fromPlace, setFromPlace] = useState('')
  const [toPlace, setToPlace] = useState('')
  const [algorithm, setAlgorithm] = useState('astar')
  const [routeSummary, setRouteSummary] = useState(null)
  const [events, setEvents] = useState([])
  const [activeRoute, setActiveRoute] = useState(null)

  // Search terms and suggestions
  const [fromSearchTerm, setFromSearchTerm] = useState('')
  const [toSearchTerm, setToSearchTerm] = useState('')
  const [fromSuggestions, setFromSuggestions] = useState([])
  const [toSuggestions, setToSuggestions] = useState([])
  const [showFromSuggestions, setShowFromSuggestions] = useState(false)
  const [showToSuggestions, setShowToSuggestions] = useState(false)

  // Focus state for suggestions
  const [fromFocused, setFromFocused] = useState(false)
  const [toFocused, setToFocused] = useState(false)

  // Traffic Simulator State
  const [selectedEdge, setSelectedEdge] = useState('')
  const [trafficLevel, setTrafficLevel] = useState('LOW')
  const [isLiveTraffic, setIsLiveTraffic] = useState(false)


  // Initialize map
  useEffect(() => {
    if (map.current || !mapContainer.current) return

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: basemap === 'satellite' ? SATELLITE_STYLE : MAP_STYLE,
      center: CAMPUS_CENTER,
      zoom: DEFAULT_ZOOM,
      attributionControl: {
        compact: true,
      },
    })

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left')

    map.current.on('load', () => {
      setMapLoaded(true)
      addMapLayers()
    })

    map.current.on('error', (event) => {
      console.error('MapLibre error:', event.error)
      setEvents(prev => [`[${new Date().toLocaleTimeString()}] Map loading error: ${event.error?.message || 'Unknown map error'}`, ...prev].slice(0, 50))
    })

    return () => {
      if (map.current) {
        map.current.remove()
        map.current = null
      }
    }
  }, [])

  // Add layers when map is loaded
  const addMapLayers = useCallback(() => {
    if (!map.current) return

    // Initialize all sources with valid empty FeatureCollections so updates are safe before remote data arrives.
    const emptyFeatureCollection = { type: 'FeatureCollection', features: [] }

    const addSourceIfMissing = (sourceId, sourceData = emptyFeatureCollection) => {
      if (!map.current.getSource(sourceId)) {
        map.current.addSource(sourceId, { type: 'geojson', data: sourceData })
      }
    }

    addSourceIfMissing('osm-data', emptyFeatureCollection)
    addSourceIfMissing('custom-features', emptyFeatureCollection)
    addSourceIfMissing('traffic', emptyFeatureCollection)
    addSourceIfMissing('route', emptyFeatureCollection)

    if (map.current.getLayer('osm-buildings')) return

    // OSM layers
    map.current.addLayer({
      id: 'osm-buildings',
      type: 'fill',
      source: 'osm-data',
      filter: ['==', ['get', 'building'], 'yes'],
      paint: {
        'fill-color': '#e2e8f0',
        'fill-opacity': 0.6,
      },
    })

    map.current.addLayer({
      id: 'osm-roads',
      type: 'line',
      source: 'osm-data',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': '#94a3b8',
        'line-width': 2,
      },
    })

    map.current.addLayer({
      id: 'osm-roads-casing',
      type: 'line',
      source: 'osm-data',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': '#64748b',
        'line-width': 4,
        'line-opacity': 0.3,
      },
      layout: { 'line-cap': 'round' },
    })

    // Custom features layers
    map.current.addLayer({
      id: 'custom-roads',
      type: 'line',
      source: 'custom-features',
      filter: ['in', ['get', 'feature_type'], ['literal', ['road', 'path', 'pedestrian_area']]],
      paint: {
        'line-color': '#3b82f6',
        'line-width': 3,
      },
    })

    map.current.addLayer({
      id: 'custom-buildings',
      type: 'fill',
      source: 'custom-features',
      filter: ['==', ['get', 'feature_type'], 'building'],
      paint: {
        'fill-color': '#dbeafe',
        'fill-opacity': 0.7,
      },
    })

    // Traffic layer
    map.current.addLayer({
      id: 'traffic-lines',
      type: 'line',
      source: 'traffic',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': ['get', 'color'],
        'line-width': 4,
        'line-opacity': 0.8,
      },
    })

    // Route layer
    map.current.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': '#2563eb',
        'line-width': 5,
        'line-opacity': 0.9,
      },
      layout: { 'line-cap': 'round', 'line-join': 'round' },
    })

    map.current.addLayer({
      id: 'route-casing',
      type: 'line',
      source: 'route',
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: {
        'line-color': '#1e40af',
        'line-width': 8,
        'line-opacity': 0.3,
      },
      layout: { 'line-cap': 'round', 'line-join': 'round' },
    })

    // Click handler for traffic info
    map.current.on('click', 'traffic-lines', (e) => {
      const feature = e.features?.[0]
      if (feature) {
        const props = feature.properties
        const popup = new maplibregl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(`
            <div style="padding: 8px;">
              <strong>${props.name || props.edge_id}</strong><br/>
              Active users: ${props.active_users}<br/>
              Traffic: <span style="color: ${props.color}">${props.traffic_level}</span><br/>
              Time: ${props.current_time_sec}s
            </div>
          `)
          .addTo(map.current)
        setActivePopup(popup)
      }
    })
  }, [])

  useEffect(() => {
    if (!map.current || !mapLoaded) return

    const source = map.current.getSource('osm-data')
    if (source && mapData?.osm) {
      source.setData(mapData.osm)
    }

    const customSource = map.current.getSource('custom-features')
    if (customSource && mapData?.custom) {
      customSource.setData(mapData.custom)
    }

    if (mapData?.osm && mapData?.custom) {
      const bounds = new maplibregl.LngLatBounds()
      const features = [...(mapData.osm?.features || []), ...(mapData.custom?.features || [])]

      for (const feature of features) {
        const geom = feature.geometry
        if (!geom) continue

        if (geom.type === 'Point') {
          bounds.extend(geom.coordinates)
        } else if (geom.type === 'LineString' || geom.type === 'MultiPoint') {
          for (const coord of geom.coordinates) {
            bounds.extend(coord)
          }
        } else if (geom.type === 'Polygon' || geom.type === 'MultiLineString') {
          const coords = geom.type === 'Polygon' ? geom.coordinates : geom.coordinates.flat()
          for (const coord of coords) {
            bounds.extend(coord)
          }
        }
      }

      if (!bounds.isEmpty()) {
        map.current.fitBounds(bounds, { padding: 50, duration: 1000 })
      }
    }
  }, [mapData, mapLoaded])

  // Update traffic layer when data changes
  useEffect(() => {
    if (!map.current || !mapLoaded || !trafficData) return

    const features = []
    for (const [edgeId, state] of Object.entries(trafficData.edges || {})) {
      if (state.geometry) {
        features.push({
          type: 'Feature',
          geometry: state.geometry,
          properties: {
            edge_id: edgeId,
            name: state.name || edgeId,
            active_users: state.active_users,
            traffic_level: state.traffic_level,
            current_time_sec: state.current_time_sec,
            color: TRAFFIC_COLORS[state.traffic_level] || TRAFFIC_COLORS.LOW,
          },
        })
      }
    }

    const source = map.current.getSource('traffic')
    if (source) {
      source.setData({ type: 'FeatureCollection', features })
    }
  }, [trafficData, mapLoaded])

  // Update route layer
  useEffect(() => {
    if (!map.current || !mapLoaded) return

    const source = map.current.getSource('route')
    if (!source) return

    if (route?.path && route.path.length > 1) {
      source.setData({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: route.path,
        },
        properties: {},
      })
    } else {
      source.setData({ type: 'FeatureCollection', features: [] })
    }
  }, [route, mapLoaded])

  // Update place markers
  useEffect(() => {
    if (!map.current || !mapLoaded) return

    // Clear existing markers
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    // Add markers for each place
    for (const place of places) {
      // Skip placing a generic marker if it's currently selected as From or To
      // to avoid overlap with the larger A/B markers.
      if (place.id === fromPlace || place.id === toPlace) continue

      const el = document.createElement('div')
      el.className = 'campus-place-marker'
      el.innerHTML = `
        <div class="marker-icon">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="6" fill="#64748b"/>
          </svg>
        </div>
        <div class="campus-place-label">${place.name}</div>
      `

      el.addEventListener('click', () => {
        onPlaceSelect?.(place)
      })

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([place.lng, place.lat])
        .addTo(map.current)

      markersRef.current.push(marker)
    }

    // Add From/To markers if selected
    const addRouteMarker = (placeId, label, color) => {
      const place = places.find(p => p.id === placeId)
      if (!place) return

      const el = document.createElement('div')
      el.className = 'route-marker-container'
      el.innerHTML = `
        <div class="marker-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="${color}"/>
            <circle cx="12" cy="9" r="2.5" fill="white"/>
          </svg>
        </div>
        <div class="route-marker-label">${label}: ${place.name}</div>
      `
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([place.lng, place.lat])
        .addTo(map.current)
      markersRef.current.push(marker)
    }

    if (fromPlace) addRouteMarker(fromPlace, 'A', '#2563eb')
    if (toPlace) addRouteMarker(toPlace, 'B', '#ef4444')

    return () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
    }
  }, [map, mapLoaded, places, onPlaceSelect, fromPlace, toPlace])

  // Fly to selected place
  useEffect(() => {
    if (!map.current || !mapLoaded || !selectedPlace) return

    map.current.flyTo({
      center: [selectedPlace.lng, selectedPlace.lat],
      zoom: 17,
      duration: 1500,
    })
  }, [selectedPlace, mapLoaded])

  // Log event to the live log
  const logEvent = useCallback((message) => {
    const time = new Date().toLocaleTimeString()
    setEvents(prev => [`[${time}] ${message}`, ...prev].slice(0, 50))
  }, [])

  // Find fastest route
  const findRoute = useCallback(async () => {
    if (!fromPlace || !toPlace) {
      alert('Please select both FROM and TO locations')
      return
    }

    const fromNode = places.find(p => p.id === fromPlace)
    const toNode = places.find(p => p.id === toPlace)

    if (!fromNode || !toNode) return

    setRouteSummary(null)
    logEvent(`Calculating route from ${fromNode.name} to ${toNode.name} using ${algorithm.toUpperCase()}...`)

    try {
      const result = await apiPost('/api/v1/routes', {
        source: { lat: fromNode.lat, lng: fromNode.lng },
        destination: { place_id: toNode.id },
        algorithm: algorithm,
      })

      if (result.success) {
        const data = result.data
        setActiveRoute(data)
        setRouteSummary({
          distance: (data.distance_m / 1000).toFixed(2),
          duration: (data.duration_sec / 60).toFixed(1),
          nodes: data.nodes_executed,
          cache: data.cache,
          algorithm: data.algorithm,
        })
        logEvent(`Route found: ${data.distance_m}m, ETA ${data.duration_sec}s, Nodes: ${data.nodes_executed}`)

        // Update MapLibre Route Layer
        const source = map.current.getSource('route')
        if (source) {
          source.setData({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: data.path,
            },
            properties: {},
          })
        }
      } else {
        logEvent(`Routing error: ${result.error?.message || 'Unknown error'}`)
        alert(result.error?.message || 'Failed to find route')
      }
    } catch (err) {
      console.error('Routing API error:', err)
      logEvent(`API error while computing route: ${err.message}`)
    }
  }, [fromPlace, toPlace, algorithm, places, logEvent])

  // Update traffic level for an edge
  const updateTraffic = useCallback(async (edgeId, level) => {
    if (!edgeId) return

    try {
      const result = await apiPost('/api/v1/traffic/update', { edge_id: edgeId, traffic_level: level })

      if (result.success) {
        logEvent(`Traffic updated: Edge ${edgeId} -> ${level}`)

        // Trigger automatic rerouting if this edge is part of the active route
        if (activeRoute && activeRoute.node_path) {
          // If the changed edge is part of our route, recalculate
          // Backend uses edge IDs, so we check if this edge ID is in the current route's sequence
          // (Assuming backend returns node_path, we might need to check edges)
          // For the demo, we re-evaluate whenever any traffic changes to ensure correctness
          findRoute()
        }
      }
    } catch (err) {
      console.error('Traffic API error:', err)
    }
  }, [activeRoute, findRoute, logEvent])

  // Live Traffic Simulation
  useEffect(() => {
    if (!isLiveTraffic) return

    const interval = setInterval(async () => {
      const levels = ['LOW', 'MEDIUM', 'HIGH', 'SEVERE', 'CLOSED']
      const randomLevel = levels[Math.floor(Math.random() * levels.length)]

      if (mapData?.edges) {
        const edgeIds = Object.keys(mapData.edges)
        const randomEdge = edgeIds[Math.floor(Math.random() * edgeIds.length)]
        await updateTraffic(randomEdge, randomLevel)
      }
    }, 7000)

    return () => clearInterval(interval)
  }, [isLiveTraffic, mapData, updateTraffic])

  // Fit bounds when map data loads
  useEffect(() => {
    if (!map.current || !mapLoaded || !mapData?.osm) return


    const bounds = new maplibregl.LngLatBounds()
    const features = mapData.osm.features || []

    for (const feature of features) {
      const geom = feature.geometry
      if (!geom) continue

      if (geom.type === 'Point') {
        bounds.extend(geom.coordinates)
      } else if (geom.type === 'LineString') {
        for (const coord of geom.coordinates) {
          bounds.extend(coord)
        }
      } else if (geom.type === 'Polygon') {
        for (const ring of geom.coordinates) {
          for (const coord of ring) {
            bounds.extend(coord)
          }
        }
      }
    }

    if (!bounds.isEmpty()) {
      map.current.fitBounds(bounds, { padding: 50, duration: 1000 })
    }
  }, [mapData, mapLoaded])

  return (
    <div className="campus-map-container">
      <div className="map-overlay-panel">
        {/* Routing Panel */}
        <div className="map-panel-card">
          <div className="panel-title">Route Planner</div>
          <div className="panel-field">
            <label className="panel-label">From</label>
            <div className="search-input-container">
              <div className="search-input-wrapper">
                <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <input
                  className="search-input"
                  type="text"
                  placeholder="Search starting place..."
                  value={fromSearchTerm}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFromSearchTerm(val);
                    const filtered = places.filter(p => p.name.toLowerCase().includes(val.toLowerCase()));
                    setFromSuggestions(filtered);
                    setShowFromSuggestions(true);
                  }}
                />
              </div>
              {showFromSuggestions && fromSuggestions.length > 0 && (
                <div className="search-suggestion-list">
                  {fromSuggestions.map(p => (
                    <button
                      key={p.id}
                      className="search-suggestion-item"
                      onClick={() => {
                        setFromPlace(p.id);
                        setFromSearchTerm(p.name);
                        setShowFromSuggestions(false);
                      }}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="panel-field">
            <label className="panel-label">To</label>
            <div className="search-input-container">
              <div className="search-input-wrapper">
                <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <input
                  className="search-input"
                  type="text"
                  placeholder="Search destination..."
                  value={toSearchTerm}
                  onChange={(e) => {
                    const val = e.target.value;
                    setToSearchTerm(val);
                    const filtered = places.filter(p => p.name.toLowerCase().includes(val.toLowerCase()));
                    setToSuggestions(filtered);
                    setShowToSuggestions(true);
                  }}
                />
              </div>
              {showToSuggestions && toSuggestions.length > 0 && (
                <div className="search-suggestion-list">
                  {toSuggestions.map(p => (
                    <button
                      key={p.id}
                      className="search-suggestion-item"
                      onClick={() => {
                        setToPlace(p.id);
                        setToSearchTerm(p.name);
                        setShowToSuggestions(false);
                      }}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="panel-field">
            <label className="panel-label">Algorithm</label>
            <select className="panel-select" value={algorithm} onChange={e => setAlgorithm(e.target.value)}>
              <option value="astar">A* (Fastest)</option>
              <option value="dijkstra">Dijkstra (Shortest)</option>
            </select>
          </div>
          <button className="panel-btn" onClick={findRoute}>Find Fastest Route</button>
          <button className="panel-btn panel-btn-secondary" onClick={() => {
            const tempFrom = fromPlace;
            const tempTo = toPlace;
            setFromPlace(tempTo);
            setToPlace(tempFrom);

            const fromNode = places.find(p => p.id === tempTo);
            const toNode = places.find(p => p.id === tempFrom);
            setFromSearchTerm(fromNode?.name || '');
            setToSearchTerm(toNode?.name || '');
          }}>Swap</button>

          {routeSummary && (
            <div className="route-summary-grid">
              <div className="summary-item">
                <span className="summary-label">Distance</span>
                <span className="summary-value">{routeSummary.distance} km</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">ETA</span>
                <span className="summary-value">{routeSummary.duration} min</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Algo</span>
                <span className="summary-value">{routeSummary.algorithm}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Cache</span>
                <span className={`summary-value ${routeSummary.cache === 'HIT' ? 'cache-hit' : 'cache-miss'}`}>
                  {routeSummary.cache}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Traffic Simulator Panel */}
        <div className="map-panel-card">
          <div className="panel-title">Traffic Simulator</div>
          <div className="panel-field">
            <label className="panel-label">Road / Edge</label>
            <select className="panel-select" value={selectedEdge} onChange={e => setSelectedEdge(e.target.value)}>
              <option value="">Select Edge</option>
              {mapData?.edges && Object.entries(mapData.edges).map(([id, edge]) => (
                <option key={id} value={id}>{edge.name || id}</option>
              ))}
            </select>
          </div>
          <div className="panel-field">
            <label className="panel-label">Traffic Level</label>
            <select className="panel-select" value={trafficLevel} onChange={e => setTrafficLevel(e.target.value)}>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="SEVERE">SEVERE</option>
              <option value="CLOSED">CLOSED</option>
            </select>
          </div>
          <button className="panel-btn" onClick={() => updateTraffic(selectedEdge, trafficLevel)}>Apply Traffic</button>
          <button className="panel-btn panel-btn-secondary" onClick={() => {
            const levels = ['LOW', 'MEDIUM', 'HIGH', 'SEVERE', 'CLOSED'];
            const randomLevel = levels[Math.floor(Math.random() * levels.length)];
            if (mapData?.edges) {
              const ids = Object.keys(mapData.edges);
              const randomId = ids[Math.floor(Math.random() * ids.length)];
              updateTraffic(randomId, randomLevel);
            }
          }}>Random Update</button>

          <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input type="checkbox" checked={isLiveTraffic} onChange={e => setIsLiveTraffic(e.target.checked)} id="live-traffic" />
            <label htmlFor="live-traffic" style={{ fontSize: '12px', fontWeight: '600' }}>Simulated Live Traffic</label>
          </div>
        </div>

        {/* Event Log */}
        <div className="map-panel-card">
          <div className="panel-title">Routing Events</div>
          <div className="event-log">
            {events.length === 0 && <div style={{ color: '#64748b', textAlign: 'center', marginTop: '20px' }}>No events yet...</div>}
            {events.map((ev, i) => (
              <div key={i} className="event-entry">{ev}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="map-layer-control">
        <button
          className={basemap === 'map' ? 'active' : ''}
          onClick={() => toggleBasemap('map')}
        >
          Map
        </button>
        <button
          className={basemap === 'satellite' ? 'active' : ''}
          onClick={() => toggleBasemap('satellite')}
        >
          Satellite
        </button>
      </div>
      <div ref={mapContainer} className="campus-map" />
      {loading && (
        <div className="map-loading">
          <div className="spinner" />
          <span>Loading map...</span>
        </div>
      )}
    </div>
  )
}
