/**
 * Trade-off dashboard component showing system metrics.
 */
import React, { useState, useEffect } from 'react'
import { apiGet } from '../../services/api'

export default function TradeoffPanel({ onClose }) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let interval
    async function fetchMetrics() {
      try {
        const result = await apiGet('/api/v1/metrics/')
        if (result.success) {
          setMetrics(result.data)
          setLoading(false)
        }
      } catch (err) {
        console.error('Metrics fetch failed:', err)
      }
    }
    fetchMetrics()
    interval = setInterval(fetchMetrics, 3000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="tradeoff-panel">
        <div className="panel-header">
          <h3>System Metrics</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="loading">Loading metrics...</div>
      </div>
    )
  }

  return (
    <div className="tradeoff-panel">
      <div className="panel-header">
        <h3>System Metrics</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <span className="metric-value">{metrics?.route_requests ?? 0}</span>
          <span className="metric-label">Route Requests</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.astar_runs ?? 0}</span>
          <span className="metric-label">A* Executions</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.astar_avg_latency_ms?.toFixed(1) ?? 0}ms</span>
          <span className="metric-label">Avg A* Latency</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.cache_hit_rate?.toFixed(1) ?? 0}%</span>
          <span className="metric-label">Cache Hit Rate</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.cache_hits ?? 0}</span>
          <span className="metric-label">Cache Hits</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.cache_misses ?? 0}</span>
          <span className="metric-label">Cache Misses</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.reroutes ?? 0}</span>
          <span className="metric-label">Reroutes</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.active_users ?? 0}</span>
          <span className="metric-label">Active Users</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.telemetry_updates ?? 0}</span>
          <span className="metric-label">Telemetry Updates</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.traffic_state_changes ?? 0}</span>
          <span className="metric-label">Traffic Changes</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.map_version ?? 0}</span>
          <span className="metric-label">Map Version</span>
        </div>
        <div className="metric-card">
          <span className="metric-value">{metrics?.traffic_version ?? 0}</span>
          <span className="metric-label">Traffic Version</span>
        </div>
      </div>

      <div className="tradeoff-info">
        <h4>Accuracy vs Computation Trade-off</h4>
        <p>
          More frequent traffic updates provide fresher data but increase processing load.
          The system balances this by only rerouting when ETA changes exceed the threshold.
        </p>
        <ul>
          <li><strong>Traffic Window:</strong> 30 seconds</li>
          <li><strong>Reroute Threshold:</strong> 15% ETA change</li>
          <li><strong>Min Reroute Interval:</strong> 30 seconds</li>
          <li><strong>Presence TTL:</strong> 45 seconds</li>
        </ul>
      </div>
    </div>
  )
}
