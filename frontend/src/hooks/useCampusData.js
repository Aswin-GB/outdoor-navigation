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
        const [mapResult, placesResult] = await Promise.all([
          getMapData(),
          getPlaces({ limit: 100 }),
        ])
        if (!cancelled) {
          setMapData(mapResult.data)
          setPlaces(placesResult.data || [])
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
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
