/**
 * User location marker component.
 */
import React, { useRef, useEffect } from 'react'
import maplibregl from 'maplibre-gl'

export default function UserLocation({ map, position, visible = true }) {
  const markerRef = useRef(null)

  useEffect(() => {
    if (!map || !position) return

    if (!markerRef.current) {
      const el = document.createElement('div')
      el.className = 'user-location-marker'
      el.innerHTML = `
        <div class="pulse"></div>
        <div class="dot"></div>
      `

      markerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([position.lng, position.lat])
        .addTo(map)
    } else {
      markerRef.current.setLngLat([position.lng, position.lat])
    }

    return () => {
      // Don't remove on unmount, just update position
    }
  }, [map, position])

  return null
}
