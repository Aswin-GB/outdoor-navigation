import React, { useState, useEffect, useCallback } from 'react'
import CampusMap from './components/map/CampusMap'
import SearchBox from './components/navigation/SearchBox'
import RoutePanel from './components/navigation/RoutePanel'
import NavigationPanel from './components/navigation/NavigationPanel'
import RerouteNotice from './components/navigation/RerouteNotice'
import TrafficPanel from './components/traffic/TrafficPanel'
import TradeoffPanel from './components/traffic/TradeoffPanel'
import TrafficDemo from './components/demo/TrafficDemo'
import MapEditor from './components/admin/MapEditor'
import { useCampusData } from './hooks/useCampusData'
import { useNavigation } from './hooks/useNavigation'
import { useTraffic } from './hooks/useTraffic'
import { useWebSocket } from './hooks/useWebSocket'
import { useGeolocation } from './hooks/useGeolocation'
import { computeRoute } from './services/routeApi'

export default function App() {
  const [view, setView] = useState('map') // 'map' | 'demo' | 'admin'
  const [selectedPlace, setSelectedPlace] = useState(null)
  const [route, setRoute] = useState(null)
  const [showTradeoff, setShowTradeoff] = useState(false)
  const [routeError, setRouteError] = useState(null)
  const [rerouteData, setRerouteData] = useState(null)

  const { mapData, places, loading: mapLoading, error: mapError } = useCampusData()
  const { navigation, startNavigation, stopNavigation, updateLocation } = useNavigation()
  const { trafficData, trafficVersion, activeUsers } = useTraffic()
  const { connected, lastMessage } = useWebSocket(navigation?.navigation_id)
  const { position, error: geoError, getCurrentPosition } = useGeolocation()

  // Handle place selection — trigger route request when we have GPS
  const handlePlaceSelect = useCallback(async (place) => {
    setSelectedPlace(place)
    setRouteError(null)

    if (!place) {
      setRoute(null)
      return
    }

    try {
      // Get current position
      const pos = await getCurrentPosition()

      if (!pos) {
        setRouteError('Unable to get your location. Please enable GPS.')
        return
      }

      const result = await computeRoute(
        { lat: pos.lat, lng: pos.lng },
        { place_id: place.id }
      )

      if (result.success) {
        setRoute(result.data)
        setRouteError(null)
      } else {
        setRouteError(result.error?.message || 'No route found.')
      }
    } catch (err) {
      setRouteError(err.message || 'Failed to compute route.')
    }
  }, [getCurrentPosition])

  // Handle navigation start
  const handleStartNavigation = useCallback(async () => {
    if (!route) return
    await startNavigation(route)
  }, [route, startNavigation])

  // Handle navigation stop
  const handleStopNavigation = useCallback(async () => {
    await stopNavigation()
    setRoute(null)
  }, [stopNavigation])

  // Handle reroute from WebSocket
  useEffect(() => {
    if (lastMessage?.event === 'route_changed') {
      setRoute(prev => ({
        ...prev,
        path: lastMessage.path,
        duration_sec: lastMessage.eta_sec,
        traffic_version: lastMessage.traffic_version,
      }))
      setRerouteData(lastMessage)
    }
  }, [lastMessage])

  return (
    <div className="app">
      {/* Top Navigation Bar */}
      <header className="app-header">
        <div className="logo">
          <svg viewBox="0 0 100 100" width="32" height="32">
            <circle cx="50" cy="50" r="45" fill="#2563eb" />
            <path d="M30 65 L50 25 L70 65 Z" fill="white" />
            <circle cx="50" cy="55" r="8" fill="#2563eb" />
          </svg>
          <h1>CampusFlow</h1>
        </div>
        <nav className="nav-tabs">
          <button
            className={view === 'map' ? 'active' : ''}
            onClick={() => setView('map')}
          >
            Map
          </button>
          <button
            className={view === 'demo' ? 'active' : ''}
            onClick={() => setView('demo')}
          >
            Traffic Demo
          </button>
          <button
            className={view === 'admin' ? 'active' : ''}
            onClick={() => setView('admin')}
          >
            Admin
          </button>
          <button
            className={showTradeoff ? 'active' : ''}
            onClick={() => setShowTradeoff(!showTradeoff)}
          >
            Metrics
          </button>
        </nav>
        <div className="header-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span>{connected ? 'Live' : 'Offline'}</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {view === 'map' && (
          <>
            <SearchBox
              places={places}
              onPlaceSelect={handlePlaceSelect}
              selectedPlace={selectedPlace}
            />
            <CampusMap
              mapData={mapData}
              places={places}
              route={route}
              trafficData={trafficData}
              selectedPlace={selectedPlace}
              onPlaceSelect={handlePlaceSelect}
              loading={mapLoading}
            />
            {mapError && (
              <div className="map-error-message" style={{ top: '1rem', left: '50%', transform: 'translateX(-50%)', bottom: 'auto' }}>
                <p>Campus map failed to load: {mapError}</p>
              </div>
            )}
            {route && (
              <RoutePanel
                route={route}
                onStartNavigation={handleStartNavigation}
                onClearRoute={() => setRoute(null)}
              />
            )}
            {navigation && (
              <NavigationPanel
                navigation={navigation}
                onStop={handleStopNavigation}
                route={route}
              />
            )}
            <TrafficPanel
              trafficData={trafficData}
              trafficVersion={trafficVersion}
              activeUsers={activeUsers}
            />
            {routeError && (
              <div className="map-error-message" style={{ top: '1rem', left: '50%', transform: 'translateX(-50%)', bottom: 'auto' }}>
                <p>{routeError}</p>
              </div>
            )}
            <RerouteNotice
              rerouteData={rerouteData}
              onDismiss={() => setRerouteData(null)}
            />
          </>
        )}

        {view === 'demo' && (
          <TrafficDemo />
        )}

        {view === 'admin' && (
          <MapEditor mapData={mapData} />
        )}

        {showTradeoff && (
          <TradeoffPanel onClose={() => setShowTradeoff(false)} />
        )}
      </main>

      {/* Map Attribution */}
      <footer className="map-attribution">
        <span>© OpenStreetMap contributors</span>
        <span>•</span>
        <span>CampusFlow</span>
      </footer>
    </div>
  )
}
