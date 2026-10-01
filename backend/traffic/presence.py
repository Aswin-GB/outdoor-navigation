"""
Active user presence tracking using Redis.
Each session has a TTL-based presence on edges.
"""
import json
import logging
import time
from typing import Optional, List

from django.conf import settings
from cache.redis import get_redis_client

logger = logging.getLogger('traffic')


class PresenceManager:
    """Manages active user presence on routing edges using Redis."""

    def __init__(self):
        self.ttl = settings.TRAFFIC_LOCATION_TTL_SECONDS

    def _presence_key(self, edge_id: str) -> str:
        return f"active_users:{edge_id}"

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def update_presence(self, session_id: str, edge_id: str, lat: float, lng: float) -> dict:
        """
        Update user presence on an edge.
        Removes previous edge membership and adds new one.
        """
        client = get_redis_client()
        if not client:
            return {'success': False, 'error': 'Redis unavailable'}

        try:
            # Get previous edge for this session
            session_data = client.get(self._session_key(session_id))
            if session_data:
                prev = json.loads(session_data)
                prev_edge = prev.get('edge_id')
                if prev_edge and prev_edge != edge_id:
                    # Remove from previous edge
                    client.srem(self._presence_key(prev_edge), session_id)
                    logger.info(f"Session {session_id} removed from edge {prev_edge}")

            # Add to new edge
            client.sadd(self._presence_key(edge_id), session_id)

            # Update session data with TTL
            session_info = {
                'edge_id': edge_id,
                'lat': lat,
                'lng': lng,
                'last_seen': time.time(),
            }
            client.setex(self._session_key(session_id), self.ttl, json.dumps(session_info))

            # Refresh edge TTL (edge expires if no active users)
            client.expire(self._presence_key(edge_id), self.ttl * 2)

            # Get updated count
            count = client.scard(self._presence_key(edge_id))

            logger.info(f"Session {session_id} on edge {edge_id}, count={count}")

            return {
                'success': True,
                'edge_id': edge_id,
                'active_users': count,
            }

        except Exception as e:
            logger.error(f"Presence update failed: {e}")
            return {'success': False, 'error': str(e)}

    def remove_presence(self, session_id: str) -> dict:
        """Remove a user's presence from all edges."""
        client = get_redis_client()
        if not client:
            return {'success': False, 'error': 'Redis unavailable'}

        try:
            session_data = client.get(self._session_key(session_id))
            if session_data:
                prev = json.loads(session_data)
                prev_edge = prev.get('edge_id')
                if prev_edge:
                    client.srem(self._presence_key(prev_edge), session_id)
                    count = client.scard(self._presence_key(prev_edge))
                    logger.info(f"Session {session_id} removed from edge {prev_edge}, count={count}")

            client.delete(self._session_key(session_id))

            return {'success': True}
        except Exception as e:
            logger.error(f"Presence removal failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_edge_count(self, edge_id: str) -> int:
        """Get active user count for an edge."""
        client = get_redis_client()
        if not client:
            return 0
        try:
            return client.scard(self._presence_key(edge_id))
        except Exception:
            return 0

    def get_all_active_edges(self) -> dict:
        """Get all edges with active users."""
        client = get_redis_client()
        if not client:
            return {}
        try:
            keys = client.keys("active_users:*")
            result = {}
            for key in keys:
                edge_id = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
                count = client.scard(key)
                if count > 0:
                    result[edge_id] = count
            return result
        except Exception:
            return {}

    def get_session_edge(self, session_id: str) -> Optional[str]:
        """Get the edge a session is currently on."""
        client = get_redis_client()
        if not client:
            return None
        try:
            data = client.get(self._session_key(session_id))
            if data:
                return json.loads(data).get('edge_id')
        except Exception:
            pass
        return None

    def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns count of removed sessions."""
        # Redis TTL handles expiration automatically
        # This method can be used for additional cleanup if needed
        return 0
