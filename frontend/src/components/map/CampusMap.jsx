/**
 * Main campus map component using Google Maps JavaScript API.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react'
import { GoogleMap, useJsApiLoader, Marker, Polyline, InfoWindow } from '@react-google-maps/api'

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

// Campus center (from actual campus data)
const CAMPUS_CENTER = { lat: 9.57, lng: 77.68 }
const DEFAULT_ZOOM = 15

// Traffic level colors
const TRAFFIC_COLORS = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  SEVERE: '#ef4444',
}

// Map container style
const containerStyle = {
  width: '100%',
  height: '100%',
}

// Map options with type control
const mapOptions = {
  mapTypeControl: true,
  mapTypeControlOptions: {
    mapTypeIds: ['roadmap', 'satellite', 'hybrid', 'terrain'],
    style: 'DEFAULT',
  },
  streetViewControl: false,
  fullscreenControl: true,
  zoomControl: true,
  scaleControl: true,
  clickableIcons: false,
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
  const mapRef = useRef(null)
  const dataLayerRef = useRef(null)
  const [activeInfoWindow, setActiveInfoWindow] = useState(null)

  // Load Google Maps API
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: GOOGLE_MAPS_API_KEY,
    libraries: ['places'],
  })

  // Handle missing API key
  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <div className="campus-map-container">
        <div className="map-config-message">
          <div className="config-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
              <circle cx="12" cy="9" r="2.5" />
            </svg>
          </div>
          <h3>Google Maps API Key Required</h3>
          <p>Please configure your Google Maps API key to display the map.</p>
          <div className="config-instructions">
            <p>1. Get an API key from <a href="https://console.cloud.google.com/google/maps-apis" target="_blank" rel="noopener noreferrer">Google Cloud Console</a></p>
            <p>2. Enable the <strong>Maps JavaScript API</strong></p>
            <p>3. Add the key to your <code>.env</code> file:</p>
            <code className="config-code">VITE_GOOGLE_MAPS_API_KEY=your_api_key_here</code>
            <p>4. Restart the development server</p>
          </div>
        </div>
      </div>
    )
  }

  // Handle load error
  if (loadError) {
    return (
      <div className="campus-map-container">
        <div className="map-config-message error">
          <div className="config-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4m0 4h.01" />
            </svg>
          </div>
          <h3>Failed to Load Google Maps</h3>
          <p>There was an error loading the Google Maps API.</p>
          <p className="error-details">{loadError.message || 'Unknown error'}</p>
        </div>
      </div>
    )
  }

  // Load GeoJSON data onto the map
  const loadGeoJson = useCallback((map) => {
    if (!map || !mapData) return

    // Remove existing data layer
    if (dataLayerRef.current) {
      dataLayerRef.current.setMap(null)
    }

    // Create new data layer
    const dataLayer = new google.maps.Data()
    
    // Add OSM features
    if (mapData.osm?.features) {
      const osmFeatures = mapData.osm.features.map(feature => ({
        type: 'Feature',
        geometry: feature.geometry,
        properties: {
          ...feature.properties,
          feature_type: feature.properties?.highway ? 'road' : 'other',
          source: 'osm',
        },
      }))
      dataLayer.addGeoJson({ type: 'FeatureCollection', features: osmFeatures })
    }

    // Add custom features
    if (mapData.custom?.features) {
      const customFeatures = mapData.custom.features.map(feature => ({
        type: 'Feature',
        geometry: feature.geometry,
        properties: {
          ...feature.properties,
          source: 'custom',
        },
      }))
      dataLayer.addGeoJson({ type: 'FeatureCollection', features: customFeatures })
    }

    // Style OSM roads
    dataLayer.setStyle((feature) => {
      const featureType = feature.getProperty('feature_type')
      const highway = feature.getProperty('highway')
      const building = feature.getProperty('building')
      const source = feature.getProperty('source')

      if (building) {
        return {
          fillColor: '#e2e8f0',
          fillOpacity: 0.6,
          strokeColor: '#94a3b8',
          strokeWeight: 1,
        }
      }

      if (featureType === 'road' || highway) {
        return {
          strokeColor: source === 'custom' ? '#3b82f6' : '#64748b',
          strokeWeight: source === 'custom' ? 3 : 2,
          strokeOpacity: 0.8,
        }
      }

      return {
        strokeColor: '#94a3b8',
        strokeWeight: 1,
        strokeOpacity: 0.5,
      }
    })

    // Add click listener for traffic info
    dataLayer.addListener('click', (event) => {
      const feature = event.feature
      const edgeId = feature.getProperty('edge_id')
      const name = feature.getProperty('name') || edgeId
      const activeUsers = feature.getProperty('active_users')
      const trafficLevel = feature.getProperty('traffic_level')
      const currentTime = feature.getProperty('current_time_sec')

      if (edgeId && activeUsers !== undefined) {
        setActiveInfoWindow({
          position: event.latLng,
          content: {
            name,
            edgeId,
            activeUsers,
            trafficLevel,
            currentTime,
          },
        })
      }
    })

    dataLayer.setMap(map)
    dataLayerRef.current = dataLayer
  }, [mapData])

  // Handle map load
  const onMapLoad = useCallback((map) => {
    mapRef.current = map
    loadGeoJson(map)
  }, [loadGeoJson])

  // Reload GeoJSON when data changes
  useEffect(() => {
    if (mapRef.current && mapData) {
      loadGeoJson(mapRef.current)
    }
  }, [mapData, loadGeoJson])

  // Update traffic overlay
  useEffect(() => {
    if (!mapRef.current || !trafficData) return

    const dataLayer = dataLayerRef.current
    if (!dataLayer) return

    // Clear existing traffic features
    dataLayer.forEach((feature) => {
      if (feature.getProperty('source') === 'traffic') {
        dataLayer.remove(feature)
      }
    })

    // Add traffic features
    for (const [edgeId, state] of Object.entries(trafficData.edges || {})) {
      if (state.geometry) {
        dataLayer.addGeoJson({
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            geometry: state.geometry,
            properties: {
              source: 'traffic',
              edge_id: edgeId,
              name: state.name || edgeId,
              active_users: state.active_users,
              traffic_level: state.traffic_level,
              current_time_sec: state.current_time_sec,
              color: TRAFFIC_COLORS[state.traffic_level] || TRAFFIC_COLORS.LOW,
            },
          }],
        })
      }
    }
  }, [trafficData])

  // Fly to selected place
  useEffect(() => {
    if (!mapRef.current || !selectedPlace) return

    mapRef.current.panTo({ lat: selectedPlace.lat, lng: selectedPlace.lng })
    mapRef.current.setZoom(17)
  }, [selectedPlace])

  // Fit bounds when map data loads
  useEffect(() => {
    if (!mapRef.current || !mapData?.osm) return

    const bounds = new google.maps.LatLngBounds()
    const features = mapData.osm.features || []

    for (const feature of features) {
      const geom = feature.geometry
      if (!geom) continue

      if (geom.type === 'Point') {
        bounds.extend({ lat: geom.coordinates[1], lng: geom.coordinates[0] })
      } else if (geom.type === 'LineString') {
        for (const coord of geom.coordinates) {
          bounds.extend({ lat: coord[1], lng: coord[0] })
        }
      } else if (geom.type === 'Polygon') {
        for (const ring of geom.coordinates) {
          for (const coord of ring) {
            bounds.extend({ lat: coord[1], lng: coord[0] })
          }
        }
      }
    }

    if (!bounds.isEmpty()) {
      mapRef.current.fitBounds(bounds, 50)
    }
  }, [mapData])

  // Route path for Polyline
  const routePath = route?.path?.map(coord => ({ lat: coord[1], lng: coord[0] })) || []

  // Traffic paths for Polylines
  const trafficPaths = Object.entries(trafficData?.edges || {}).map(([edgeId, state]) => ({
    edgeId,
    path: state.geometry?.coordinates?.map(coord => ({ lat: coord[1], lng: coord[0] })) || [],
    color: TRAFFIC_COLORS[state.traffic_level] || TRAFFIC_COLORS.LOW,
    state,
  }))

  if (!isLoaded) {
    return (
      <div className="campus-map-container">
        <div className="map-loading">
          <div className="spinner" />
          <span>Loading Google Maps...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="campus-map-container">
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={CAMPUS_CENTER}
        zoom={DEFAULT_ZOOM}
        options={mapOptions}
        onLoad={onMapLoad}
      >
        {/* Place markers */}
        {places.map(place => (
          <Marker
            key={place.id}
            position={{ lat: place.lat, lng: place.lng }}
            title={place.name}
            onClick={() => onPlaceSelect?.(place)}
            icon={{
              url: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#2563eb"/>
                  <circle cx="12" cy="9" r="2.5" fill="white"/>
                </svg>
              `),
              scaledSize: new google.maps.Size(24, 24),
              anchor: new google.maps.Point(12, 24),
            }}
          />
        ))}

        {/* Route polyline */}
        {routePath.length > 1 && (
          <>
            <Polyline
              path={routePath}
              options={{
                strokeColor: '#1e40af',
                strokeWeight: 8,
                strokeOpacity: 0.3,
                clickable: false,
              }}
            />
            <Polyline
              path={routePath}
              options={{
                strokeColor: '#2563eb',
                strokeWeight: 5,
                strokeOpacity: 0.9,
                clickable: false,
              }}
            />
          </>
        )}

        {/* Traffic polylines */}
        {trafficPaths.map(({ edgeId, path, color }) => (
          path.length > 1 && (
            <Polyline
              key={edgeId}
              path={path}
              options={{
                strokeColor: color,
                strokeWeight: 4,
                strokeOpacity: 0.8,
                clickable: false,
              }}
            />
          )
        ))}

        {/* Traffic info window */}
        {activeInfoWindow && (
          <InfoWindow
            position={activeInfoWindow.position}
            onCloseClick={() => setActiveInfoWindow(null)}
          >
            <div style={{ padding: '8px' }}>
              <strong>{activeInfoWindow.content.name}</strong><br />
              Active users: {activeInfoWindow.content.activeUsers}<br />
              Traffic: <span style={{ color: activeInfoWindow.content.color || TRAFFIC_COLORS[activeInfoWindow.content.trafficLevel] }}>
                {activeInfoWindow.content.trafficLevel}
              </span><br />
              Time: {activeInfoWindow.content.currentTime}s
            </div>
          </InfoWindow>
        )}
      </GoogleMap>

      {loading && (
        <div className="map-loading">
          <div className="spinner" />
          <span>Loading map data...</span>
        </div>
      )}
    </div>
  )
}
