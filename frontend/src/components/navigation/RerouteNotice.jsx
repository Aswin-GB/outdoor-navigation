/**
 * Reroute notification component.
 */
import React, { useState, useEffect } from 'react'

export default function RerouteNotice({ rerouteData, onDismiss }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (rerouteData) {
      setVisible(true)
      const timer = setTimeout(() => {
        setVisible(false)
        onDismiss?.()
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [rerouteData, onDismiss])

  if (!visible || !rerouteData) return null

  return (
    <div className="reroute-notice">
      <div className="reroute-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        </svg>
      </div>
      <div className="reroute-content">
        <strong>Route Updated</strong>
        <span>Traffic change detected. New ETA: {Math.round(rerouteData.eta_sec / 60)} min</span>
      </div>
      <button className="close-btn" onClick={() => { setVisible(false); onDismiss?.() }}>
        ×
      </button>
    </div>
  )
}
