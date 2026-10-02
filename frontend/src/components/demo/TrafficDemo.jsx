/**
 * Live traffic demonstration page.
 *
 * Supports:
 * - real GPS location sharing
 * - simulated users on any routing edge
 * - live edge traffic state
 * - manual traffic-level simulation
 * - reset simulation
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useGeolocation } from '../../hooks/useGeolocation'
import { getMapData } from '../../services/mapApi'
import {
  getTrafficForEdge,
  sendTelemetry,
  stopSharing,
  simulateTraffic,
  applyTrafficLevel,
} from '../../services/trafficApi'

const TRAFFIC_LEVELS = [
  'LOW',
  'MODERATE',
  'HIGH',
  'SEVERE',
  'CLOSED',
]

export default function TrafficDemo() {
  const [sessionId, setSessionId] = useState(null)
  const [sharing, setSharing] = useState(false)
  const [currentEdge, setCurrentEdge] = useState(null)
  const [activeUsers, setActiveUsers] = useState(0)
  const [trafficLevel, setTrafficLevel] = useState('LOW')
  const [currentTime, setCurrentTime] = useState(0)

  const [edges, setEdges] = useState({})
  const [simEdgeId, setSimEdgeId] = useState('')
  const [simCount, setSimCount] = useState(1)
  const [simulatedUsers, setSimulatedUsers] = useState(0)

  const [manualLevel, setManualLevel] = useState('HIGH')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)

  const pollRef = useRef(null)

  const {
    position,
    error: geoError,
    startWatching,
    stopWatching,
  } = useGeolocation()

  useEffect(() => {
    setSessionId(
      `session_${Date.now()}_${Math.random()
        .toString(36)
        .slice(2, 9)}`,
    )
  }, [])

  // Load routing edges for the simulator dropdown.
  useEffect(() => {
    let cancelled = false

    async function loadEdges() {
      try {
        const result = await getMapData()

        if (cancelled) return

        if (result?.success && result?.data?.edges) {
          setEdges(result.data.edges)

          const ids = Object.keys(result.data.edges)
          if (!simEdgeId && ids.length > 0) {
            setSimEdgeId(ids[0])
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(`Unable to load routing edges: ${err.message}`)
        }
      }
    }

    loadEdges()

    return () => {
      cancelled = true
    }
  }, [simEdgeId])

  const refreshSelectedEdge = useCallback(async () => {
    if (!simEdgeId) return

    try {
      const result = await getTrafficForEdge(simEdgeId)

      if (result?.success && result?.data) {
        const data = result.data
        setActiveUsers(data.active_users ?? 0)
        setTrafficLevel(data.traffic_level ?? 'LOW')
        setCurrentTime(data.current_time_sec ?? 0)
        setSimulatedUsers(data.active_users ?? 0)
      }
    } catch (err) {
      console.error('Traffic state refresh failed:', err)
    }
  }, [simEdgeId])

  // Poll selected edge so multiple browser sessions are visible.
  useEffect(() => {
    refreshSelectedEdge()

    pollRef.current = setInterval(
      refreshSelectedEdge,
      2000,
    )

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }
    }
  }, [refreshSelectedEdge])

  const handleStartSharing = useCallback(() => {
    if (!sessionId) return

    setError(null)
    setMessage(null)
    setSharing(true)
    startWatching()
  }, [sessionId, startWatching])

  const handleStopSharing = useCallback(async () => {
    setSharing(false)
    stopWatching()

    if (sessionId) {
      try {
        await stopSharing(sessionId)
      } catch (err) {
        console.error('Stop sharing failed:', err)
      }
    }

    setCurrentEdge(null)
  }, [sessionId, stopWatching])

  // Send real GPS telemetry whenever position changes.
  useEffect(() => {
    if (!sharing || !position || !sessionId) return

    let cancelled = false

    async function sendUpdate() {
      try {
        const result = await sendTelemetry(
          sessionId,
          position.lat,
          position.lng,
          new Date().toISOString(),
          null,
        )

        if (cancelled) return

        if (result.success) {
          setCurrentEdge(result.edge_id)
          setActiveUsers(result.active_users ?? 0)
          setTrafficLevel(result.traffic_level ?? 'LOW')
          setCurrentTime(result.current_time_sec ?? 0)
        } else {
          setError(
            result.error?.message ||
              result.error ||
              'Telemetry failed',
          )
        }
      } catch (err) {
        if (!cancelled) {
          setError(`Telemetry failed: ${err.message}`)
        }
      }
    }

    sendUpdate()

    const interval = setInterval(
      sendUpdate,
      5000,
    )

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [sharing, position, sessionId])

  const handleSimulation = useCallback(
    async (action) => {
      if (!simEdgeId && action !== 'reset') {
        setError('Select an edge first.')
        return
      }

      setLoading(true)
      setError(null)
      setMessage(null)

      try {
        const result = await simulateTraffic(
          action,
          simEdgeId || null,
          simCount,
        )

        if (!result.success) {
          throw new Error(
            result.error?.message ||
              result.error ||
              'Simulation failed',
          )
        }

        setMessage(
          action === 'reset'
            ? 'Simulation reset successfully.'
            : `Simulation ${action} successful.`,
        )

        if (result.edge_id) {
          setCurrentEdge(result.edge_id)
          setActiveUsers(result.active_users ?? 0)
          setTrafficLevel(result.traffic_level ?? 'LOW')
          setCurrentTime(result.current_time_sec ?? 0)
          setSimulatedUsers(result.active_users ?? 0)
        }

        await refreshSelectedEdge()
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    },
    [simEdgeId, simCount, refreshSelectedEdge],
  )

  const handleManualLevel = useCallback(async () => {
    if (!simEdgeId) {
      setError('Select an edge first.')
      return
    }

    setLoading(true)
    setError(null)
    setMessage(null)

    try {
      const result = await applyTrafficLevel(
        simEdgeId,
        manualLevel,
      )

      if (!result.success) {
        throw new Error(
          result.error?.message ||
            result.error ||
            'Traffic update failed',
        )
      }

      setMessage(
        `Traffic set to ${manualLevel}.`,
      )

      await refreshSelectedEdge()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [simEdgeId, manualLevel, refreshSelectedEdge])

  const selectedEdge = edges[simEdgeId]

  return (
    <div className="traffic-demo">
      <div className="demo-header">
        <h2>Traffic Demo</h2>
        <p>
          Real GPS traffic and simulated-user testing for CampusFlow.
        </p>
      </div>

      {message && (
        <div className="success-message">
          {message}
        </div>
      )}

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <div className="demo-content">
        <div className="demo-section">
          <h3>Your Location</h3>

          <div className="sharing-status">
            <span
              className={`status-dot ${sharing ? 'active' : ''}`}
            />
            <span>
              {sharing
                ? 'Sharing location'
                : 'Not sharing'}
            </span>
          </div>

          {position && (
            <div className="location-info">
              <p>
                Lat: {position.lat.toFixed(6)}
              </p>
              <p>
                Lng: {position.lng.toFixed(6)}
              </p>
              <p>
                Accuracy: ±{Math.round(position.accuracy)}m
              </p>
            </div>
          )}

          {geoError && (
            <div className="error-message">
              Location error: {geoError}
            </div>
          )}

          <div className="demo-actions">
            {!sharing ? (
              <button
                className="btn btn-primary"
                onClick={handleStartSharing}
              >
                Start Sharing
              </button>
            ) : (
              <button
                className="btn btn-danger"
                onClick={handleStopSharing}
              >
                Stop Sharing
              </button>
            )}
          </div>

          {currentEdge && (
            <div className="current-road">
              <h4>Current Road</h4>
              <p>Edge: {currentEdge}</p>
              <p>Active Users: {activeUsers}</p>
              <p>
                Traffic:{' '}
                <strong>{trafficLevel}</strong>
              </p>
              <p>
                Current Travel Time:{' '}
                {Number(currentTime).toFixed(1)}s
              </p>
            </div>
          )}
        </div>

        <div className="demo-section">
          <h3>Simulated Traffic</h3>
          <p className="simulated-label">
            SIMULATED DATA
          </p>

          <div className="simulator-controls">
            <div className="form-group">
              <label htmlFor="sim-edge">
                Road / Edge
              </label>
              <select
                id="sim-edge"
                value={simEdgeId}
                onChange={(event) => {
                  setSimEdgeId(event.target.value)
                  setMessage(null)
                  setError(null)
                }}
              >
                <option value="">
                  Select Edge
                </option>

                {Object.entries(edges).map(
                  ([id, edge]) => (
                    <option key={id} value={id}>
                      {edge.name || id}
                    </option>
                  ),
                )}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="sim-count">
                Users
              </label>
              <input
                id="sim-count"
                type="number"
                value={simCount}
                min="1"
                max="100"
                onChange={(event) =>
                  setSimCount(
                    Math.max(
                      1,
                      Math.min(
                        100,
                        Number.parseInt(
                          event.target.value,
                          10,
                        ) || 1,
                      ),
                    ),
                  )
                }
              />
            </div>

            <div className="simulator-buttons">
              <button
                className="btn btn-secondary"
                disabled={loading}
                onClick={() =>
                  handleSimulation('add')
                }
              >
                Add Users
              </button>

              <button
                className="btn btn-secondary"
                disabled={loading}
                onClick={() =>
                  handleSimulation('remove')
                }
              >
                Remove Users
              </button>

              <button
                className="btn btn-danger"
                disabled={loading}
                onClick={() =>
                  handleSimulation('reset')
                }
              >
                Reset
              </button>
            </div>
          </div>

          {selectedEdge && (
            <div className="current-road">
              <p>
                Selected: {selectedEdge.name || simEdgeId}
              </p>
              <p>
                Simulated/Active Users: {simulatedUsers}
              </p>
            </div>
          )}
        </div>

        <div className="demo-section">
          <h3>Manual Traffic Level</h3>
          <p>
            Useful for demonstrating immediate dynamic edge-weight
            changes without changing GPS position.
          </p>

          <div className="simulator-controls">
            <div className="form-group">
              <label htmlFor="manual-level">
                Traffic Level
              </label>
              <select
                id="manual-level"
                value={manualLevel}
                onChange={(event) =>
                  setManualLevel(event.target.value)
                }
              >
                {TRAFFIC_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>

            <button
              className="btn btn-primary"
              disabled={loading || !simEdgeId}
              onClick={handleManualLevel}
            >
              Apply Traffic Level
            </button>
          </div>
        </div>

        <div className="demo-section">
          <h3>How to Demo</h3>
          <ol className="demo-instructions">
            <li>Choose a road/edge.</li>
            <li>Add 4 users → MODERATE.</li>
            <li>Add 4 more → HIGH.</li>
            <li>Watch the active-user count and travel time update.</li>
            <li>Open another browser/device and repeat the test.</li>
            <li>Use Manual Traffic Level for a deterministic HIGH/SEVERE/CLOSED demonstration.</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
