"""Stateful coordination for a single member's flood incident.

The Discord gateway may enqueue many messages before the first timeout reaches
Discord. This coordinator groups them into one incident so enforcement stays
predictable: one timeout, deletion of every flagged message, and no log storm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class FloodIncident:
    expires_at: datetime
    message_ids: set[int] = field(default_factory=set)


class FloodEnforcementCoordinator:
    """Aggregate flood decisions per guild/member for the timeout cooldown."""

    def __init__(self) -> None:
        self._incidents: dict[tuple[int, int], FloodIncident] = {}

    def begin_or_join(self, guild_id: int, user_id: int, message_id: int, duration: timedelta, now: datetime) -> bool:
        """Return ``True`` only for the decision that starts the incident."""
        key = (guild_id, user_id)
        incident = self._incidents.get(key)
        if incident is None or incident.expires_at <= now:
            self._incidents[key] = FloodIncident(expires_at=now + duration, message_ids={message_id})
            return True
        incident.message_ids.add(message_id)
        return False

    def abort(self, guild_id: int, user_id: int) -> None:
        """Allow retrying if the primary timeout could not be applied."""
        self._incidents.pop((guild_id, user_id), None)

    def message_ids(self, guild_id: int, user_id: int) -> tuple[int, ...]:
        incident = self._incidents.get((guild_id, user_id))
        return tuple(incident.message_ids) if incident else ()
