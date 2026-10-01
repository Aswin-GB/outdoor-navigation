/**
 * Traffic demo component for live hackathon demonstration.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useGeolocation } from '../../hooks/useGeolocation'
import { sendTelemetry, stopSharing, simulateTraffic } from '../../services/trafficApi'

export default function TrafficDemo() {
  const [sessionId, setSessionId] = useState(null)
  const [sharing, setSharing] = useState(false)
  const [currentEdge, setCurrentEdge] = useState(null)
  const [activeUsers, setActiveUsers] = useState(0)
  const [trafficLevel, setTrafficLevel] = useState('LOW')
  const [simulated, setSimulated] = useState(false)
  const [simEdgeId, setSimEdgeId] = useState('')
  const [simCount, setSimCount] = useState(1)
  const { position, error: geoError, startWatching, stopWatching } = useGeolocation()
  const intervalRef = useRef(null)

  // Generate session ID
  useEffect(() => {
    setSessionId(`session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`)
  }, [])

  // Start sharing location
  const handleStartSharing = useCallback(() => {
    if (!sessionId) return
    setSharing(true)
    startWatching()
  }, [sessionId, startWatching])

  // Stop sharing location
  const handleStopSharing = useCallback(async () => {
    setSharing(false)
    stopWatching()
    if (sessionId) {
      await stopSharing(sessionId)
    }
    setCurrentEdge(null)
    setActiveUsers(0)
  }, [sessionId, stopWatching])

  // Send telemetry updates
  useEffect(() => {
    if (!sharing || !position || !sessionId) return

    const sendUpdate = async () => {
      try {
        const result = await sendTelemetry(
          sessionId,
          position.lat,
          position.lng,
          new Date().toISOString()
        )
        if (result.success) {
          setCurrentEdge(result.edge_id)
          setActiveUsers(result.active_users)
          setTrafficLevel(result.traffic_level)
        }
      } catch (err) {
        console.error('Telemetry failed:', err)
      }
    }

    sendUpdate()
    intervalRef.current = setInterval(sendUpdate, 5000)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [sharing, position, sessionId])

  // Simulated traffic controls
  const handleSimulate = async (action) => {
    if (!simEdgeId) return
    try {
      const result = await simulateTraffic(action, simEdgeId, simCount)
      if (result.success) {
        setSimulated(true)
      }
    } catch (err) {
      console.error('Simulation failed:', err)
    }
  }

  return (
    <div className="traffic-demo">
      <div className="demo-header">
        <h2>Traffic Demo</h2>
        <p>Share your location to contribute to campus traffic analysis</p>
      </div>

      <div className="demo-content">
        {/* Location Sharing Section */}
        <div className="demo-section">
          <h3>Your Location</h3>
          <div className="sharing-status">
            <span className={`status-dot ${sharing ? 'active' : ''}`} />
            <span>{sharing ? 'Sharing location' : 'Not sharing'}</span>
          </div>

          {position && (
            <div className="location-info">
              <p>Lat: {position.lat.toFixed(6)}</p>
              <p>Lng: {position.lng.toFixed(6)}</p>
              <p>Accuracy: ±{Math.round(position.accuracy)}m</p>
            </div>
          )}

          {geoError && (
            <div className="error-message">
              Location error: {geoError}
            </div>
          )}

          <div className="demo-actions">
            {!sharing ? (
              <button className="btn btn-primary" onClick={handleStartSharing}>
                Start Sharing
              </button>
            ) : (
              <button className="btn btn-danger" onClick={handleStopSharing}>
                Stop Sharing
              </button>
            )}
          </div>

          {currentEdge && (
            <div className="current-road">
              <h4>Current Road</h4>
              <p>Edge: {currentEdge}</p>
              <p>Active Users: {activeUsers}</p>
              <p>Traffic Level: <span className={`traffic-${trafficLevel.toLowerCase()}`}>{trafficLevel}</span></p>
            </div>
          )}
        </div>

        {/* Simulator Section */}
        <div className="demo-section">
          <h3>Traffic Simulator</h3>
          <p className="simulated-label">SIMULATED DATA</p>

          <div className="simulator-controls">
            <div className="form-group">
              <label>Edge ID</label>
              <input
                type="text"
                value={simEdgeId}
                onChange={(e) => setSimEdgeId(e.target.value)}
                placeholder="Enter edge ID"
              />
            </div>
            <div className="form-group">
              <label>User Count</label>
              <input
                type="number"
                value={simCount}
                onChange={(e) => setSimCount(parseInt(e.target.value) || 1)}
                min="1"
                max="50"
              />
            </div>
            <div className="simulator-buttons">
              <button className="btn btn-secondary" onClick={() => handleSimulate('add')}>
                Add Users
              </button>
              <button className="btn btn-secondary" onClick={() => handleSimulate('remove')}>
                Remove Users
              </button>
              <button className="btn btn-danger" onClick={() => handleSimulate('reset')}>
                Reset
              </button>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="demo-section">
          <h3>How to Demo</h3>
          <ol className="demo-instructions">
            <li>Open this page on multiple devices</li>
            <li>Each person clicks "Start Sharing"</li>
            <li>Grant location permission</li>
            <li>Walk to the same road</li>
            <li>Watch traffic levels change in real-time</li>
            <li>Use the simulator to add virtual users</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
