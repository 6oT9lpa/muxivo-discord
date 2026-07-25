from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException

import activity.server.dependencies as activity_dependencies
from activity.server.schemas.dev_blog import DevBlogEmbedPayload, DevBlogPostPayload
from activity.server.schemas.voice_rooms import VoiceRoomUpdatePayload
from activity.server.services.dashboard_service import ActivityDashboardService
from activity.server.services.dev_blog_service import DevBlogService
from activity.server.services.logs_service import LogsService
from activity.server.services.stats_service import ActivityStatsService
from activity.server.services.voice_room_service import VoiceRoomService
from activity.server.utils.dev_blog_messages import build_dev_blog_message
from activity.server.utils.welcome_config import normalize_config


@pytest_asyncio.fixture
async def activity_db(postgres_test_db):
    manager = postgres_test_db
    previous_db = activity_dependencies._db
    activity_dependencies._db = manager
    try:
        yield manager
    finally:
        activity_dependencies._db = previous_db


@pytest.mark.asyncio
async def test_dashboard_returns_empty_metrics_when_optional_tables_are_missing(activity_db, monkeypatch):
    service = ActivityDashboardService()

    async def ensure_dashboard(*_):
        return {"id": "42", "username": "admin"}, {"available_modules": ["dashboard"]}

    async def no_latency():
        return None

    await activity_db.execute("DROP TABLE messages")
    await activity_db.execute("DROP TABLE streamers")
    await activity_db.commit()
    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_dashboard)
    monkeypatch.setattr(service._discord, "measure_latency", no_latency)

    dashboard = await service.get_dashboard(100, "token")

    assert dashboard.metrics.ai_checks_today == 0
    assert dashboard.metrics.ai_flagged_today == 0
    assert dashboard.metrics.creator_sources == 0
    assert dashboard.audit == []


def test_dashboard_serializes_postgres_audit_datetime():
    service = ActivityDashboardService()
    event = service._to_audit_event(
        {
            "id": 1,
            "guild_id": 100,
            "actor_id": 42,
            "actor_name": "Admin",
            "target_id": None,
            "target_name": None,
            "event_type": "activity_roles_synced",
            "details": "Synced roles",
            "created_at": datetime(2026, 7, 1, 23, 54, 21),
        }
    )

    assert event.created_at == "2026-07-01 23:54:21"


def test_ai_classifier_log_presentation_preserves_decision_details():
    row = LogsService._to_ai_moderation_log(
        {
            "id": 9,
            "guild_id": 100,
            "channel_id": 200,
            "message_id": 300,
            "user_id": 400,
            "risk_score": 74,
            "decision_action": "REVIEW",
            "proposed_action": "DELETE",
            "primary_label": "SCAM",
            "labels_json": ["SCAM", "TOXIC"],
            "status": "SUCCESS",
            "latency_ms": 19,
            "message_content": "Suspicious promotion",
            "created_at": datetime(2026, 7, 26, 2, 40),
        }
    )

    assert row["id"] == "ai-9"
    assert row["event_type"] == "ai_moderation_decision"
    assert row["details"]["fields"][2] == {"name": "Decision", "value": "REVIEW", "inline": True}
    assert row["details"]["fields"][-1]["value"] == "Suspicious promotion"


@pytest.mark.asyncio
async def test_logs_service_lists_actor_dropdown_values(activity_db, monkeypatch):
    service = LogsService()

    async def ensure_logs(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_logs)
    await activity_db.execute(
        """
        INSERT INTO guild_event_logs (guild_id, actor_id, actor_name, target_id, target_name, event_type, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (100, 42, "Admin", 99, "Member", "voice_join", "{'channel': 'Main'}"),
    )
    await activity_db.execute(
        """
        INSERT INTO message_logs (guild_id, message_id, channel_id, author_id, author_name, content, event_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (100, 1, 2, 77, "Writer", "hello", "message"),
    )
    await activity_db.commit()

    actors = await service.list_actors(100, "token")

    assert {"id": "42", "name": "Admin"} in actors
    assert {"id": "77", "name": "Writer"} in actors
    assert {"id": "99", "name": "Member"} not in actors


@pytest.mark.asyncio
async def test_logs_service_includes_persisted_ai_classifier_decisions(activity_db, monkeypatch):
    """Classifier output is visible in the same feed as the other server audit events."""
    service = LogsService()
    guild_id, channel_id, message_id, user_id = 987654, 987655, 987656, 987657

    async def ensure_logs(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_logs)
    await activity_db.execute(
        """INSERT INTO ai_moderation_events
           (guild_id, channel_id, message_id, user_id, risk_score, decision_action, proposed_action, primary_label, labels_json, confidence, latency_ms, status)
           VALUES (?, ?, ?, ?, ?, 'REVIEW', 'DELETE', 'SCAM', '[\"SCAM\", \"TOXIC\"]'::jsonb, ?, ?, 'SUCCESS')""",
        (guild_id, channel_id, message_id, user_id, 74, 0.91, 19),
    )
    await activity_db.execute(
        "INSERT INTO message_logs (guild_id, channel_id, message_id, author_id, author_name, content, event_type) VALUES (?, ?, ?, ?, ?, ?, 'message')",
        (guild_id, channel_id, message_id, user_id, "Member", "Suspicious promotion",),
    )
    await activity_db.commit()

    logs = await service.list_logs(guild_id, "all", None, "", 20, "token")
    ai_only = await service.list_logs(guild_id, "ai", None, "SCAM", 20, "token")

    decision = next(row for row in logs["audit"] if row["event_type"] == "ai_moderation_decision")
    assert decision["actor_name"] == "AI classifier"
    assert decision["details"]["fields"][2] == {"name": "Decision", "value": "REVIEW", "inline": True}
    assert decision["details"]["fields"][-1]["value"] == "Suspicious promotion"
    assert len(ai_only["audit"]) == 1


@pytest.mark.asyncio
async def test_server_stats_returns_thirty_daily_chart_points(activity_db, monkeypatch):
    service = ActivityStatsService()

    async def ensure_stats(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    async def channels(*_, **__):
        return []

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_stats)
    monkeypatch.setattr(service._discord, "safe_bot_request", channels)

    payload = await service.get_server_stats(100, 30, "token")

    assert len(payload["daily"]) == 30


def test_welcome_config_serializes_snowflakes_as_strings():
    config = normalize_config(
        {
            "rules_channel_id": 1515345606816694403,
            "roles_channel_id": 1515345606816694404,
        },
        1515345326909952052,
    )

    assert config["guild_id"] == "1515345326909952052"
    assert config["rules_channel_id"] == "1515345606816694403"
    assert config["roles_channel_id"] == "1515345606816694404"


@pytest.mark.asyncio
async def test_dev_blog_publishes_ten_images_in_one_components_v2_message(activity_db, monkeypatch):
    service = DevBlogService()
    sent_payloads = []

    async def ensure_developer(*_):
        return {"id": "42", "username": "dev"}, {"is_developer": True}

    async def bot_request(method, path, *, json_body=None, **_):
        sent_payloads.append((method, path, json_body))
        return {"id": "900"}

    monkeypatch.setattr(service._access_service, "ensure_developer_or_admin", ensure_developer)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO server_channel_purposes (guild_id, purpose, channel_id) VALUES (?, ?, ?)",
        (100, "dev_blog", 555),
    )
    await activity_db.commit()
    payload = DevBlogPostPayload(
        guild_id=100,
        title="Release",
        embeds=[DevBlogEmbedPayload(title=f"Part {index}", description="body", image_url=f"https://example.com/{index}.png") for index in range(10)],
        image_render_mode="gallery_bottom",
        status="published",
    )

    result = await service.create_post(payload, "token")

    assert result["message_id"] == 900
    assert len(sent_payloads) == 1
    message_payload = sent_payloads[0][2]
    assert message_payload["flags"] == 32768
    assert len(message_payload["components"]) == 1
    media_gallery = message_payload["components"][0]["components"][1]
    assert media_gallery["type"] == 12
    assert len(media_gallery["items"]) == 10


@pytest.mark.asyncio
async def test_dev_blog_default_ping_is_spoiler_component_outside_container(activity_db, monkeypatch):
    service = DevBlogService()
    sent_payloads = []

    async def ensure_developer(*_):
        return {"id": "42", "username": "dev"}, {"is_developer": True}

    async def bot_request(method, path, *, json_body=None, **_):
        sent_payloads.append(json_body)
        return {"id": "901"}

    monkeypatch.setattr(service._access_service, "ensure_developer_or_admin", ensure_developer)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO server_channel_purposes (guild_id, purpose, channel_id) VALUES (?, ?, ?)",
        (100, "dev_blog", 555),
    )
    await activity_db.execute(
        "INSERT INTO server_role_purposes (guild_id, purpose, role_id) VALUES (?, ?, ?)",
        (100, "ping_dev", 777),
    )
    await activity_db.commit()

    await service.create_post(
        DevBlogPostPayload(
            guild_id=100,
            title="Release",
            embeds=[DevBlogEmbedPayload(description="body")],
            status="published",
        ),
        "token",
    )

    message_payload = sent_payloads[0]

    assert "content" not in message_payload
    assert message_payload["allowed_mentions"] == {"roles": ["777"]}
    assert message_payload["components"][0] == {"type": 10, "content": "||<@&777>||"}
    assert message_payload["components"][1]["type"] == 17


def test_dev_blog_can_render_images_between_text_blocks():
    payload = DevBlogPostPayload(
        guild_id=100,
        title="Release",
        embeds=[
            DevBlogEmbedPayload(title="Part 1", description="Text 1", image_url="https://example.com/1.png"),
            DevBlogEmbedPayload(title="Part 2", description="Text 2", image_url="https://example.com/2.png"),
        ],
        image_render_mode="inline_between_text",
    )

    message = build_dev_blog_message(payload)
    components = message["components"][0]["components"]

    assert [component["type"] for component in components] == [10, 10, 12, 10, 12]
    assert components[2]["items"][0]["media"]["url"] == "https://example.com/1.png"
    assert components[4]["items"][0]["media"]["url"] == "https://example.com/2.png"


@pytest.mark.asyncio
async def test_voice_room_serializes_snowflakes_and_runs_member_actions(activity_db, monkeypatch):
    service = VoiceRoomService()
    calls = []

    async def ensure_voice(*_):
        return {"id": "42", "username": "owner"}, {"access_level": "moderator", "is_admin": False}

    async def bot_request(method, path, *, json_body=None, **_):
        calls.append((method, path, json_body))
        if method == "GET":
            return {"id": "1515345606816694403", "name": "Room", "permission_overwrites": []}
        return {"id": "1515345606816694403", "name": "Room"}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    monkeypatch.setattr(service._discord, "safe_bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (1515345606816694403, 100, 42, "Room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (1515345606816694403, 100, 42),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (1515345606816694403, 100, 99),
    )
    await activity_db.commit()

    rooms = await service.list_rooms(100, "token")
    await service.update_room(
        1515345606816694403,
        VoiceRoomUpdatePayload(guild_id=100, invite_user_id=99, kick_user_id=99, ban_user_id=99, rtc_region="rotterdam"),
        "token",
    )

    assert rooms[0]["channel_id"] == "1515345606816694403"
    assert rooms[0]["owner_id"] == "42"
    assert rooms[0]["admin_id"] is None
    assert rooms[0]["voice_member_ids"] == ["42", "99"]
    assert any(call[1] == "/guilds/100/members/99" and call[2] == {"channel_id": None} for call in calls)


def test_voice_room_rejects_removed_europe_region():
    with pytest.raises(ValueError):
        VoiceRoomUpdatePayload(guild_id=100, rtc_region="europe")


@pytest.mark.asyncio
async def test_voice_room_assigns_admin_without_changing_owner(activity_db, monkeypatch):
    service = VoiceRoomService()
    calls = []

    async def ensure_voice(*_):
        return {"id": "42", "username": "owner"}, {"access_level": "ordinary", "is_admin": False}

    async def bot_request(method, path, *, json_body=None, **_):
        calls.append((method, path, json_body))
        if method == "GET":
            return {"id": "700", "name": "Room", "permission_overwrites": []}
        return {"id": "700", "name": "Room"}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (700, 100, 42, "Room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (700, 100, 99),
    )
    await activity_db.commit()

    await service.update_room(700, VoiceRoomUpdatePayload(guild_id=100, admin_id=99), "token")
    room = await activity_db.fetch_one("SELECT owner_id, admin_id FROM voice_rooms WHERE channel_id = ?", (700,))

    assert room["owner_id"] == 42
    assert room["admin_id"] == 99
    assert any(call[0] == "PATCH" and call[1] == "/channels/700" for call in calls)


@pytest.mark.asyncio
async def test_voice_room_rejects_admin_assignment_when_target_is_not_in_room(activity_db, monkeypatch):
    service = VoiceRoomService()

    async def ensure_voice(*_):
        return {"id": "42", "username": "owner"}, {"access_level": "ordinary", "is_admin": False}

    async def bot_request(method, path, *, json_body=None, **_):
        if method == "GET":
            return {"id": "701", "name": "Room", "permission_overwrites": []}
        return {"id": "701", "name": "Room"}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (701, 100, 42, "Room"),
    )
    await activity_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.update_room(701, VoiceRoomUpdatePayload(guild_id=100, admin_id=99), "token")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_voice_room_claims_free_admin_without_changing_owner(activity_db, monkeypatch):
    service = VoiceRoomService()

    async def ensure_voice(*_):
        return {"id": "99", "username": "member"}, {"access_level": "moderator", "is_admin": False}

    async def bot_request(method, path, *, json_body=None, **_):
        if method == "GET":
            return {"id": "702", "name": "Room", "permission_overwrites": []}
        return {"id": "702", "name": "Room"}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (702, 100, 42, "Room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (702, 100, 99),
    )
    await activity_db.commit()

    await service.update_room(702, VoiceRoomUpdatePayload(guild_id=100, claim_admin=True), "token")
    room = await activity_db.fetch_one("SELECT owner_id, admin_id FROM voice_rooms WHERE channel_id = ?", (702,))

    assert room["owner_id"] == 42
    assert room["admin_id"] == 99


@pytest.mark.asyncio
async def test_voice_room_rejects_self_and_owner_removal(activity_db, monkeypatch):
    service = VoiceRoomService()

    async def ensure_voice(*_):
        return {"id": "99", "username": "admin"}, {"access_level": "ordinary", "is_admin": False}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, admin_id, name) VALUES (?, ?, ?, ?, ?)",
        (703, 100, 42, 99, "Room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (703, 100, 99),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (703, 100, 42),
    )
    await activity_db.commit()

    with pytest.raises(HTTPException) as self_exc:
        await service.update_room(703, VoiceRoomUpdatePayload(guild_id=100, kick_user_id=99), "token")
    with pytest.raises(HTTPException) as owner_exc:
        await service.update_room(703, VoiceRoomUpdatePayload(guild_id=100, ban_user_id=42), "token")

    assert self_exc.value.status_code == 400
    assert owner_exc.value.status_code == 400


@pytest.mark.asyncio
async def test_voice_room_ban_clears_current_admin(activity_db, monkeypatch):
    service = VoiceRoomService()
    calls = []

    async def ensure_voice(*_):
        return {"id": "42", "username": "owner"}, {"access_level": "ordinary", "is_admin": False}

    async def bot_request(method, path, *, json_body=None, **_):
        calls.append((method, path, json_body))
        if method == "GET":
            return {
                "id": "704",
                "name": "Room",
                "permission_overwrites": [{"id": "99", "type": 1, "allow": "285212688", "deny": "0"}],
            }
        return {"id": "704", "name": "Room"}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)
    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, admin_id, name) VALUES (?, ?, ?, ?, ?)",
        (704, 100, 42, 99, "Room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_room_members (channel_id, guild_id, user_id) VALUES (?, ?, ?)",
        (704, 100, 99),
    )
    await activity_db.commit()

    await service.update_room(704, VoiceRoomUpdatePayload(guild_id=100, ban_user_id=99), "token")
    room = await activity_db.fetch_one("SELECT admin_id FROM voice_rooms WHERE channel_id = ?", (704,))
    patch_call = next(call for call in calls if call[0] == "PATCH" and call[1] == "/channels/704")
    overwrites = patch_call[2]["permission_overwrites"]

    assert room["admin_id"] is None
    assert overwrites == [{"id": "99", "type": 1, "allow": "0", "deny": "1048576"}]
    assert any(
        call[0] == "PATCH"
        and call[1] == "/guilds/100/members/99"
        and call[2] == {"channel_id": None}
        for call in calls
    )
