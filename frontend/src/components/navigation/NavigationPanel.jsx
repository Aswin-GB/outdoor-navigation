/**
 * Active navigation panel component.
 */
import React from 'react'

export default function NavigationPanel({ navigation, onStop, route }) {
  if (!navigation) return null

  const formatDuration = (seconds) => {
    const mins = Math.round(seconds / 60)
    if (mins < 60) return `${mins} min`
    const hours = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hours}h ${remainingMins}m`
  }

  return (
    <div className="navigation-panel">
      <div className="nav-header">
        <div className="nav-status">
          <span className="nav-indicator active" />
          <span>Navigating</span>
        </div>
        <button className="close-btn" onClick={onStop}>×</button>
      </div>

      {route && (
        <div className="nav-info">
          <div className="nav-stat">
            <span className="nav-value">{formatDuration(route.duration_sec)}</span>
            <span className="nav-label">ETA</span>
          </div>
          <div className="nav-stat">
            <span className="nav-value">{route.traffic_version}</span>
            <span className="nav-label">Traffic v</span>
          </div>
        </div>
      )}

      <div className="nav-details">
        <div className="detail-row">
          <span className="detail-label">Navigation ID:</span>
          <span className="detail-value">{navigation.navigation_id?.slice(0, 8)}...</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Status:</span>
          <span className="detail-value">{navigation.status}</span>
        </div>
      </div>

      <button className="btn btn-danger btn-full" onClick={onStop}>
        Stop Navigation
      </button>
    </div>
  )
}
