"""
Navigation session models.
"""
import uuid
from django.db import models


class NavigationSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        STOPPED = "stopped", "Stopped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    route_id = models.CharField(
        max_length=255,
        db_index=True,
    )

    source = models.JSONField(default=dict)
    destination = models.JSONField(default=dict)

    current_position = models.JSONField(
        null=True,
        blank=True,
    )

    current_edge = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    # Route state used by traffic analyzer
    route_nodes = models.JSONField(
        default=list,
        blank=True,
    )

    route_edges = models.JSONField(
        default=list,
        blank=True,
    )

    current_eta_sec = models.FloatField(
        default=0.0,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    last_seen_at = models.DateTimeField(
        auto_now=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Navigation {self.id} - {self.status}"