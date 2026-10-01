import React, { useState, useEffect, useCallback } from 'react'
import CampusMap from './components/map/CampusMap'
import SearchBox from './components/navigation/SearchBox'
import RoutePanel from './components/navigation/RoutePanel'
import NavigationPanel from './components/navigation/NavigationPanel'
import TrafficPanel from './components/traffic/TrafficPanel'
import TradeoffPanel from './components/traffic/TradeoffPanel'
import TrafficDemo from './components/demo/TrafficDemo'
import MapEditor from './components/admin/MapEditor'
import { useCampusData } from './hooks/useCampusData'
import { useNavigation } from './hooks/useNavigation'
import { useTraffic } from './hooks/useTraffic'
import { useWebSocket } from './hooks/useWebSocket'

export default function App() {
  const [view, setView] = useState('map') // 'map' | 'demo' | 'admin'
  const [selectedPlace, setSelectedPlace] = useState(null)
  const [route, setRoute] = useState(null)
  const [showTradeoff, setShowTradeoff] = useState(false)

  const { mapData, places, loading: mapLoading, error: mapError } = useCampusData()
  const { navigation, startNavigation, stopNavigation, updateLocation } = useNavigation()
  const { trafficData, trafficVersion, activeUsers } = useTraffic()
  const { connected, lastMessage } = useWebSocket(navigation?.navigation_id)

  // Handle place selection
  const handlePlaceSelect = useCallback((place) => {
    setSelectedPlace(place)
  }, [])

  // Handle route request
  const handleRouteRequest = useCallback(async (source, destination) => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1/routes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source,
          destination: { place_id: destination.id },
          mode: 'walking',
        }),
      })
      const data = await response.json()
      if (data.success) {
        setRoute(data.data)
      }
    } catch (err) {
      console.error('Route request failed:', err)
    }
  }, [])

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
