/**
 * Routing API service.
 */
import { apiPost } from './api'

export async function computeRoute(source, destination, mode = 'walking') {
  return apiPost('/api/v1/routes', { source, destination, mode })
}

export async function reroute(routeId, currentPosition, destination, reason = 'traffic_change') {
  return apiPost(`/api/v1/routes/${routeId}/reroute`, {
    current_position: currentPosition,
    destination,
    reason,
  })
}
