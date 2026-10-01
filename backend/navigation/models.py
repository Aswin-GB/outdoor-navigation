"""
Navigation session models.
"""
from django.db import models
import uuid


class NavigationSession(models.Model):
    """Tracks an active navigation session."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        STOPPED = 'stopped', 'Stopped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route_id = models.CharField(max_length=255, db_index=True)
    source = models.JSONField()
    destination = models.JSONField()
    current_position = models.JSONField(null=True, blank=True)
    current_edge = models.CharField(max_length=255, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Navigation {self.id} - {self.status}"
