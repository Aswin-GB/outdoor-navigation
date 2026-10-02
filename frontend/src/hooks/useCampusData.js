/**
 * Hook for loading campus map data and places.
 */
import { useState, useEffect } from 'react'
import { getMapData } from '../services/mapApi'
import { getPlaces } from '../services/placeApi'

export function useCampusData() {
  const [mapData, setMapData] = useState(null)
  const [places, setPlaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        setLoading(true)
        setError(null)

        const [mapResult, placesResult] = await Promise.allSettled([
          getMapData(),
          getPlaces({ limit: 100 }),
        ])

        if (cancelled) return

        if (mapResult.status === 'fulfilled' && mapResult.value?.data) {
          setMapData(mapResult.value.data)
        } else {
          const message = mapResult.reason?.message || 'Campus map failed to load.'
          setError(message)
          setMapData(null)
        }

        if (placesResult.status === 'fulfilled') {
          setPlaces(placesResult.value?.data || [])
        } else {
          console.error('Places request failed:', placesResult.reason)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Campus data failed to load.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  return { mapData, places, loading, error }
}
