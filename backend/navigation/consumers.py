"""
WebSocket consumer for real-time navigation updates.
"""
import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('navigation')


class NavigationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for navigation session updates."""

    async def connect(self):
        self.navigation_id = self.scope['url_route']['kwargs']['navigation_id']
        self.room_group_name = f'navigation_{self.navigation_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected for navigation {self.navigation_id}")

        # Send connection confirmation
        await self.send_json({
            'event': 'connection_established',
            'navigation_id': self.navigation_id,
        })

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected for navigation {self.navigation_id}")

    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        event = content.get('event')

        if event == 'ping':
            await self.send_json({'event': 'pong'})
        elif event == 'navigation_state':
            await self.send_json({
                'event': 'navigation_state',
                'navigation_id': self.navigation_id,
                'status': 'active',
            })

    async def traffic_update(self, event):
        """Send traffic update to WebSocket."""
        await self.send_json({
            'event': 'traffic_update',
            'edge_id': event['edge_id'],
            'active_user_count': event['active_user_count'],
            'traffic_level': event['traffic_level'],
            'current_time_sec': event['current_time_sec'],
            'traffic_version': event['traffic_version'],
        })

    async def route_changed(self, event):
        """Send route change notification to WebSocket."""
        await self.send_json({
            'event': 'route_changed',
            'route_id': event['route_id'],
            'reason': event['reason'],
            'eta_sec': event['eta_sec'],
            'path': event['path'],
            'traffic_version': event['traffic_version'],
            'map_version': event['map_version'],
        })

    async def navigation_state(self, event):
        """Send navigation state update."""
        await self.send_json({
            'event': 'navigation_state',
            'navigation_id': self.navigation_id,
            'status': event.get('status', 'active'),
            'current_edge': event.get('current_edge'),
        })

    async def error(self, event):
        """Send error message to client."""
        await self.send_json({
            'event': 'error',
            'code': event.get('code', 'UNKNOWN_ERROR'),
            'message': event.get('message', 'An error occurred.'),
        })
