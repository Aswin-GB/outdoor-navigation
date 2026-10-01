/**
 * Main campus map component using MapLibre GL JS.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const MAP_STYLE = import.meta.env.VITE_MAP_STYLE_URL || 'https://demotiles.maplibre.org/style.json'

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

  // Initialize map
  useEffect(() => {
    if (map.current || !mapContainer.current) return

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
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

    // OSM data source
    map.current.addSource('osm-data', {
      type: 'geojson',
      data: mapData?.osm || { type: 'FeatureCollection', features: [] },
    })

    // Custom features source
    map.current.addSource('custom-features', {
      type: 'geojson',
      data: mapData?.custom || { type: 'FeatureCollection', features: [] },
    })

    // Traffic source
    map.current.addSource('traffic', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })

    // Route source
    map.current.addSource('route', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })

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
  }, [mapData])

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
      const el = document.createElement('div')
      el.className = 'place-marker'
      el.innerHTML = `
        <div class="marker-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#2563eb"/>
            <circle cx="12" cy="9" r="2.5" fill="white"/>
          </svg>
        </div>
        <div class="marker-label">${place.name}</div>
      `

      el.addEventListener('click', () => {
        onPlaceSelect?.(place)
      })

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([place.lng, place.lat])
        .addTo(map.current)

      markersRef.current.push(marker)
    }

    return () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
    }
  }, [map, mapLoaded, places, onPlaceSelect])

  // Fly to selected place
  useEffect(() => {
    if (!map.current || !mapLoaded || !selectedPlace) return

    map.current.flyTo({
      center: [selectedPlace.lng, selectedPlace.lat],
      zoom: 17,
      duration: 1500,
    })
  }, [selectedPlace, mapLoaded])

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
