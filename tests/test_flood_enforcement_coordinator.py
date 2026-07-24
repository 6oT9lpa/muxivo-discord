from datetime import datetime, timedelta

from application.services.flood_enforcement_coordinator import FloodEnforcementCoordinator


def test_flood_burst_creates_one_incident_and_tracks_every_message() -> None:
    coordinator = FloodEnforcementCoordinator()
    now = datetime(2026, 7, 24, 10, 0, 0)

    assert coordinator.begin_or_join(1, 2, 10, timedelta(minutes=10), now) is True
    assert coordinator.begin_or_join(1, 2, 11, timedelta(minutes=10), now + timedelta(seconds=1)) is False

    assert set(coordinator.message_ids(1, 2)) == {10, 11}


def test_flood_incident_expires_after_cooldown() -> None:
    coordinator = FloodEnforcementCoordinator()
    now = datetime(2026, 7, 24, 10, 0, 0)
    coordinator.begin_or_join(1, 2, 10, timedelta(minutes=1), now)

    assert coordinator.begin_or_join(1, 2, 11, timedelta(minutes=1), now + timedelta(minutes=1)) is True
