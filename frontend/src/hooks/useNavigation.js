/**
 * Hook for navigation session management.
 */
import { useState, useCallback } from 'react'
import { apiPost } from '../services/api'

export function useNavigation() {
  const [navigation, setNavigation] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const startNavigation = useCallback(async (route) => {
    try {
      setLoading(true)
      const result = await apiPost('/api/v1/navigation/start', {
        route_id: route.route_id,
        source: route.source,
        destination: route.destination,
        route_nodes: route.node_path,
        route_edges: route.edge_path,
        duration_sec: route.duration_sec,
      })
      if (result.success) {
        setNavigation(result.data)
        setError(null)
      } else {
        setError(result.error?.message || 'Failed to start navigation')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const stopNavigation = useCallback(async () => {
    if (!navigation) return
    try {
      await apiPost('/api/v1/navigation/stop', {
        navigation_id: navigation.navigation_id,
      })
      setNavigation(null)
    } catch (err) {
      setError(err.message)
    }
  }, [navigation])

  const updateLocation = useCallback(async (lat, lng, edgeId) => {
    if (!navigation) return
    try {
      await apiPost('/api/v1/navigation/location', {
        navigation_id: navigation.navigation_id,
        lat,
        lng,
        edge_id: edgeId,
      })
    } catch (err) {
      console.error('Location update failed:', err)
    }
  }, [navigation])

  return { navigation, loading, error, startNavigation, stopNavigation, updateLocation }
}
