/**
 * Routing API service.
 */
import { apiPost } from './api'

export async function computeRoute(source, destination, mode = 'walking', algorithm = 'astar') {
  return apiPost('/api/v1/routes', { source, destination, mode, algorithm })
}

export async function reroute(routeId, currentPosition, destination, reason = 'traffic_change') {
  return apiPost(`/api/v1/routes/${routeId}/reroute`, {
    current_position: currentPosition,
    destination,
    reason,
  })
}
