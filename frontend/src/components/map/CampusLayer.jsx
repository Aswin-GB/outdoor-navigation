/**
 * Campus layer component for rendering OSM and custom features.
 */
import React from 'react'

export default function CampusLayer({ map, data, visible = true }) {
  if (!map || !data) return null

  // This component is used as a building block within CampusMap
  // The actual layer management is handled by CampusMap

  return null
}
