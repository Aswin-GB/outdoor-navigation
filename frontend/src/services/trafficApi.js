/**
 * Traffic API service.
 */
import { apiGet, apiPost } from './api'

export async function getTraffic() {
  return apiGet('/api/v1/traffic/')
}

export async function getTrafficForEdge(edgeId) {
  return apiGet(`/api/v1/traffic/${encodeURIComponent(edgeId)}`)
}

export async function sendTelemetry(
  sessionId,
  lat,
  lng,
  timestamp,
  navigationId = null,
) {
  return apiPost('/api/v1/telemetry/location', {
    session_id: sessionId,
    navigation_id: navigationId,
    lat,
    lng,
    timestamp,
  })
}

export async function stopSharing(sessionId) {
  return apiPost('/api/v1/telemetry/stop', {
    session_id: sessionId,
  })
}

export async function simulateTraffic(
  action,
  edgeId = null,
  count = 1,
) {
  return apiPost('/api/v1/traffic/simulate', {
    action,
    edge_id: edgeId,
    count,
  })
}

export async function applyTrafficLevel(edgeId, trafficLevel) {
  return apiPost('/api/v1/traffic/update', {
    edge_id: edgeId,
    traffic_level: trafficLevel,
  })
}
