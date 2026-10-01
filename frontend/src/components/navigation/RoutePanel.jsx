/**
 * Route information panel component.
 */
import React from 'react'

export default function RoutePanel({ route, onStartNavigation, onClearRoute }) {
  if (!route) return null

  const formatDuration = (seconds) => {
    const mins = Math.round(seconds / 60)
    if (mins < 60) return `${mins} min`
    const hours = Math.floor(mins / 60)
    const remainingMins = mins % 60
    return `${hours}h ${remainingMins}m`
  }

  const formatDistance = (meters) => {
    if (meters < 1000) return `${Math.round(meters)} m`
    return `${(meters / 1000).toFixed(1)} km`
  }

  return (
    <div className="route-panel">
      <div className="route-header">
        <h3>Route</h3>
        <button className="close-btn" onClick={onClearRoute}>×</button>
      </div>

      <div className="route-stats">
        <div className="stat">
          <span className="stat-value">{formatDuration(route.duration_sec)}</span>
          <span className="stat-label">Duration</span>
        </div>
        <div className="stat">
          <span className="stat-value">{formatDistance(route.distance_m)}</span>
          <span className="stat-label">Distance</span>
        </div>
        <div className="stat">
          <span className="stat-value">{route.algorithm}</span>
          <span className="stat-label">Algorithm</span>
        </div>
      </div>

      <div className="route-details">
        <div className="detail-row">
          <span className="detail-label">Cache:</span>
          <span className={`detail-value cache-${route.cache?.toLowerCase()}`}>
            {route.cache || 'N/A'}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Map Version:</span>
          <span className="detail-value">{route.map_version}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">Traffic Version:</span>
          <span className="detail-value">{route.traffic_version}</span>
        </div>
      </div>

      <button className="btn btn-primary btn-full" onClick={onStartNavigation}>
        Start Navigation
      </button>
    </div>
  )
}
