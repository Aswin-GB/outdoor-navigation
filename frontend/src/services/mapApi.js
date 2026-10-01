/**
 * Map data API service.
 */
import { apiGet, apiPost, apiPut, apiDelete } from './api'

export async function getMapData() {
  return apiGet('/api/v1/map/')
}

export async function getMapVersion() {
  return apiGet('/api/v1/map/version')
}

export async function getFeatures() {
  return apiGet('/api/v1/map/features')
}

export async function createFeature(feature) {
  return apiPost('/api/v1/map/features', feature)
}

export async function updateFeature(id, feature) {
  return apiPut(`/api/v1/map/features/${id}`, feature)
}

export async function deleteFeature(id) {
  return apiDelete(`/api/v1/map/features/${id}`)
}
