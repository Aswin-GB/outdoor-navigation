/**
 * Traffic API service.
 */
import { apiGet, apiPost } from './api'

export async function getTraffic() {
  return apiGet('/api/v1/traffic/')
}

export async function getTrafficForEdge(edgeId) {
  return apiGet(`/api/v1/traffic/${edgeId}`)
}

export async function sendTelemetry(sessionId, lat, lng, timestamp) {
  return apiPost('/api/v1/telemetry/location', {
    session_id: sessionId,
    lat,
    lng,
    timestamp,
  })
}

export async function stopSharing(sessionId) {
  return apiPost('/api/v1/telemetry/stop', { session_id: sessionId })
}

export async function simulateTraffic(action, edgeId, count) {
  return apiPost('/api/v1/traffic/simulate', { action, edge_id: edgeId, count })
}
