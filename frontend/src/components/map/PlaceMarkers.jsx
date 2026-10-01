/**
 * Place markers component for displaying campus POIs.
 */
import React, { useRef, useEffect } from 'react'
import maplibregl from 'maplibre-gl'

export default function PlaceMarkers({ map, places = [], onPlaceSelect, visible = true }) {
  const markersRef = useRef([])

  useEffect(() => {
    if (!map || !places.length) return

    // Clear existing markers
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    // Add markers for each place
    for (const place of places) {
      const el = document.createElement('div')
      el.className = 'place-marker'
      el.innerHTML = `
        <div class="marker-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" fill="#2563eb"/>
            <circle cx="12" cy="9" r="2.5" fill="white"/>
          </svg>
        </div>
        <div class="marker-label">${place.name}</div>
      `

      el.addEventListener('click', () => {
        onPlaceSelect?.(place)
      })

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([place.lng, place.lat])
        .addTo(map)

      markersRef.current.push(marker)
    }

    return () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []
    }
  }, [map, places, onPlaceSelect])

  return null
}
