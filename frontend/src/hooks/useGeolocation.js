/**
 * Hook for browser geolocation.
 */
import { useState, useEffect, useCallback, useRef } from 'react'

export function useGeolocation() {
  const [position, setPosition] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const watchId = useRef(null)

  const getCurrentPosition = useCallback(() => {
    if (!navigator.geolocation) {
      const locationError = new Error('Geolocation is not supported by your browser')
      setError(locationError.message)
      return Promise.reject(locationError)
    }

    setLoading(true)

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const nextPosition = {
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
          }
          setPosition(nextPosition)
          setLoading(false)
          setError(null)
          resolve(nextPosition)
        },
        (err) => {
          setError(err.message)
          setLoading(false)
          reject(err)
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      )
    })
  }, [])

  const startWatching = useCallback(() => {
    if (watchId.current !== null) return

    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser')
      return
    }

    setLoading(true)
    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPosition({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        })
        setLoading(false)
        setError(null)
      },
      (err) => {
        setError(err.message)
        setLoading(false)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    )
  }, [])

  const stopWatching = useCallback(() => {
    if (watchId.current !== null) {
      navigator.geolocation.clearWatch(watchId.current)
      watchId.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      if (watchId.current !== null) {
        navigator.geolocation.clearWatch(watchId.current)
      }
    }
  }, [])

  return { position, error, loading, getCurrentPosition, startWatching, stopWatching }
}
