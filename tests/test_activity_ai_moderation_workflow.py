import pytest
import pytest_asyncio
from pydantic import SecretStr

import activity.server.dependencies as activity_dependencies
import activity.server.services.ai_moderation_service as ai_service_module
from activity.server.schemas.ai_moderation_channels import AiModerationChannelsPayload
from activity.server.schemas.ai_moderation_policy import AiModerationPolicyPayload
from activity.server.schemas.ai_moderation_review import AiModerationReviewUpdatePayload
from activity.server.services.ai_moderation_service import AiModerationService


@pytest_asyncio.fixture
async def activity_ai_db(postgres_test_db):
    previous_db = activity_dependencies._db
    activity_dependencies._db = postgres_test_db
    try:
        yield postgres_test_db
    finally:
        activity_dependencies._db = previous_db


@pytest.mark.asyncio
async def test_ai_moderation_persists_exact_discord_snowflakes_and_policy(activity_ai_db, monkeypatch):
    """This covers the Activity save-and-reload workflow with production-size Discord IDs."""
    service = AiModerationService()
    guild_id = 1515345326909952052
    selected_channel_id = 1515345606816694403
    rejected_channel_id = 1515345606816694404
    validated_channel_sets: list[set[int]] = []

    async def ensure_access(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    async def filter_channels(received_guild_id: str, channel_ids: set[int]):
        assert received_guild_id == str(guild_id)
        validated_channel_sets.append(channel_ids)
        return {selected_channel_id}

    async def list_channels(*_):
        return []

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    monkeypatch.setattr(service._discord_service, "filter_moderation_channel_ids", filter_channels)
    monkeypatch.setattr(service._discord_service, "list_channels", list_channels)
    monkeypatch.setattr(ai_service_module, "get_db", lambda: activity_ai_db)

    # Pydantic accepts decimal strings without changing their value before database storage.
    channels_payload = AiModerationChannelsPayload(
        guild_id=str(guild_id),
        channel_ids=[str(selected_channel_id), str(rejected_channel_id)],
    )
    saved_channels = await service.save_channels(channels_payload, "token")

    policy_payload = AiModerationPolicyPayload(
        guild_id=str(guild_id),
        policy={
            "blacklist_words": ["Fraud", "fraud", "spam"],
            "allowed_domains": ["Example.COM"],
            "labels": {},
            "blacklist_action": "DELETE_WARN",
            "unapproved_domain_action": "REVIEW",
        },
    )
    saved_policy = await service.save_policy(policy_payload, "token")

    reloaded = await service.get_settings(guild_id, "token")

    assert validated_channel_sets == [{selected_channel_id, rejected_channel_id}]
    assert saved_channels["channels"] == [str(selected_channel_id)]
    assert saved_policy["policy"]["blacklist_words"] == ["fraud", "spam"]
    assert reloaded["channels"] == [str(selected_channel_id)]
    assert reloaded["policy"]["allowed_domains"] == ["example.com"]


@pytest.mark.asyncio
async def test_review_queue_requires_trusted_labeling_admin_and_audits_updates(activity_ai_db, monkeypatch):
    service = AiModerationService()
    guild_id, actor_id = 3001, 4001

    async def module_access(*_):
        return {"id": str(actor_id)}, {"is_admin": True}

    async def context(*_):
        return {"user": {"id": str(actor_id)}}

    monkeypatch.setattr(service._access_service, "ensure_module_access", module_access)
    monkeypatch.setattr(service._access_service, "fetch_user_context", context)
    monkeypatch.setattr(ai_service_module, "get_db", lambda: activity_ai_db)

    await activity_ai_db.execute("INSERT INTO trusted_guilds (guild_id) VALUES (?)", (guild_id,))
    await activity_ai_db.execute("INSERT INTO labeling_roles (guild_id, user_id, role, assigned_by) VALUES (?, ?, 'ADMIN', ?)", (guild_id, actor_id, actor_id))
    await activity_ai_db.execute(
        "INSERT INTO ai_moderation_review_items (guild_id, channel_id, message_id, user_id, message_text, risk_score, severity, action, labels_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]'::jsonb)",
        (guild_id, 1, 2, 3, "test", 40, 2, "REVIEW"),
    )

    page = await service.list_review_items(guild_id, "token", "OPEN", 20, 0)
    assert page["total"] == 1
    item = page["items"][0]
    updated = await service.update_review_item(item["id"], AiModerationReviewUpdatePayload(
        guild_id=guild_id, revision=item["revision"], message_text="corrected", risk_score=55, severity=4,
        action="DELETE", status="RESOLVED",
    ), "token")
    assert updated["status"] == "RESOLVED"
    assert updated["revision"] == 2
    audit = await service.list_review_audit(guild_id, "token", 20, 0)
    assert audit["total"] == 1
    assert audit["items"][0]["action"] == "RESOLVED"


@pytest.mark.asyncio
async def test_review_queue_allows_trusted_labeler(activity_ai_db, monkeypatch):
    service = AiModerationService()
    guild_id, actor_id = 3003, 4003

    async def context(*_): return {"user": {"id": str(actor_id)}}
    monkeypatch.setattr(service._access_service, "fetch_user_context", context)
    monkeypatch.setattr(ai_service_module, "get_db", lambda: activity_ai_db)
    await activity_ai_db.execute("INSERT INTO trusted_guilds (guild_id) VALUES (?)", (guild_id,))
    await activity_ai_db.execute("INSERT INTO labeling_roles (guild_id, user_id, role, assigned_by) VALUES (?, ?, 'LABELER', ?)", (guild_id, actor_id, actor_id))

    assert await service.can_access_review_queue(guild_id, "token") is True


@pytest.mark.asyncio
async def test_test_mode_simulation_never_creates_dataset_event(activity_ai_db, monkeypatch):
    service = AiModerationService()
    guild_id = 3002

    async def module_access(*_): return {"id": "42"}, {"is_admin": True}
    monkeypatch.setattr(service._access_service, "ensure_module_access", module_access)
    monkeypatch.setattr(ai_service_module, "get_db", lambda: activity_ai_db)

    class _Config:
        ai_moderator_api_url = "http://test"
        ai_moderator_internal_api_key = SecretStr("key")
        ai_moderator_request_timeout_seconds = 1

    class _Client:
        def __init__(self, *_): pass
        async def simulate(self, _):
            return {"risk_score": 50, "severity": 3, "confidence": 0.9, "latency_ms": 2, "decision_action": "WARN", "primary_label": "TOXIC", "labels": ["TOXIC"], "rule_matches": [], "execution_plan": ["WARN"]}

    monkeypatch.setattr(ai_service_module, "get_config", lambda: _Config())
    monkeypatch.setattr(ai_service_module, "AiModeratorApiClient", _Client)
    await activity_ai_db.execute("INSERT INTO ai_moderation_settings (guild_id, policy_json) VALUES (?, '{\"test_mode\": true}'::jsonb)", (guild_id,))
    result = await service.simulate(guild_id, "test message", "token")
    assert result["dataset_event_created"] is False
    assert result["model_action"] == "WARN"
    assert result["policy_action"] == "WARN"
