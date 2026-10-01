/**
 * Places API service.
 */
import { apiGet } from './api'

export async function getPlaces(params = {}) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.category) query.set('category', params.category)
  if (params.limit) query.set('limit', params.limit)
  const qs = query.toString()
  return apiGet(`/api/v1/places${qs ? `?${qs}` : ''}`)
}

export async function getPlace(id) {
  return apiGet(`/api/v1/places/${id}`)
}
