/**
 * Traffic information panel component.
 */
import React from 'react'

const TRAFFIC_COLORS = {
  LOW: '#22c55e',
  MODERATE: '#eab308',
  HIGH: '#f97316',
  SEVERE: '#ef4444',
}

export default function TrafficPanel({ trafficData, trafficVersion, activeUsers }) {
  const edges = trafficData?.edges || {}
  const edgeList = Object.entries(edges)

  return (
    <div className="traffic-panel">
      <div className="traffic-header">
        <h3>Traffic</h3>
        <span className="traffic-version">v{trafficVersion}</span>
      </div>

      <div className="traffic-summary">
        <div className="summary-stat">
          <span className="summary-value">{activeUsers}</span>
          <span className="summary-label">Active Users</span>
        </div>
        <div className="summary-stat">
          <span className="summary-value">{edgeList.length}</span>
          <span className="summary-label">Congested Roads</span>
        </div>
      </div>

      {edgeList.length > 0 && (
        <div className="traffic-list">
          {edgeList.slice(0, 5).map(([edgeId, state]) => (
            <div key={edgeId} className="traffic-item">
              <div className="traffic-indicator" style={{ backgroundColor: TRAFFIC_COLORS[state.traffic_level] || TRAFFIC_COLORS.LOW }} />
              <div className="traffic-info">
                <span className="traffic-name">{state.name || edgeId}</span>
                <span className="traffic-detail">
                  {state.active_users} users • {state.current_time_sec}s
                </span>
              </div>
              <span className="traffic-level" style={{ color: TRAFFIC_COLORS[state.traffic_level] || TRAFFIC_COLORS.LOW }}>
                {state.traffic_level}
              </span>
            </div>
          ))}
        </div>
      )}

      {edgeList.length === 0 && (
        <div className="traffic-empty">
          <p>No active traffic data</p>
          <p className="traffic-hint">Open the Traffic Demo to simulate users</p>
        </div>
      )}
    </div>
  )
}
