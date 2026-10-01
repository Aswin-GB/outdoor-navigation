/**
 * Hook for traffic data management.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { getTraffic } from '../services/trafficApi'

export function useTraffic(pollInterval = 5000) {
  const [trafficData, setTrafficData] = useState(null)
  const [trafficVersion, setTrafficVersion] = useState(0)
  const [activeUsers, setActiveUsers] = useState(0)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef(null)

  const fetchTraffic = useCallback(async () => {
    try {
      const result = await getTraffic()
      if (result.success) {
        setTrafficData(result.data)
        setTrafficVersion(result.data.traffic_version || 0)
        const totalUsers = Object.values(result.data.edges || {}).reduce(
          (sum, e) => sum + (e.active_users || 0), 0
        )
        setActiveUsers(totalUsers)
        setLoading(false)
      }
    } catch (err) {
      console.error('Traffic fetch failed:', err)
    }
  }, [])

  useEffect(() => {
    fetchTraffic()
    intervalRef.current = setInterval(fetchTraffic, pollInterval)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchTraffic, pollInterval])

  return { trafficData, trafficVersion, activeUsers, loading, refresh: fetchTraffic }
}
