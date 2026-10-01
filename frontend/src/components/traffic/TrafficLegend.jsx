/**
 * Traffic legend component.
 */
import React from 'react'

const TRAFFIC_LEVELS = [
  { level: 'LOW', color: '#22c55e', range: '0-3 users' },
  { level: 'MODERATE', color: '#eab308', range: '4-7 users' },
  { level: 'HIGH', color: '#f97316', range: '8-12 users' },
  { level: 'SEVERE', color: '#ef4444', range: '13+ users' },
]

export default function TrafficLegend() {
  return (
    <div className="traffic-legend">
      <div className="legend-title">Traffic Level</div>
      {TRAFFIC_LEVELS.map(({ level, color, range }) => (
        <div key={level} className="legend-item">
          <span className="legend-color" style={{ backgroundColor: color }} />
          <span className="legend-label">{level}</span>
          <span className="legend-range">{range}</span>
        </div>
      ))}
    </div>
  )
}
