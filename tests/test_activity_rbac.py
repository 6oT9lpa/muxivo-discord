from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException

import activity.server.dependencies as activity_dependencies
import activity.server.services.rbac_service as rbac_service_module
from activity.server.schemas.dev_blog import DevBlogEmbedPayload, DevBlogPostPayload
from activity.server.schemas.voice_rooms import VoiceRoomUpdatePayload
from activity.server.services.access_service import ActivityAccessService
from activity.server.services.dev_blog_service import DevBlogService
from activity.server.services.rbac_service import ActivityRbacService
from activity.server.services.voice_room_service import VoiceRoomService
from activity.server.services.welcome_service import ActivityWelcomeService
from infrastructure.database.repositories.role_repository import RoleRepository


@pytest_asyncio.fixture
async def activity_db(postgres_test_db):
    manager = postgres_test_db
    previous_db = activity_dependencies._db
    activity_dependencies._db = manager
    try:
        yield manager
    finally:
        activity_dependencies._db = previous_db


def _context(*, roles: set[int] | None = None, discord_admin: bool = False):
    return {
        "user": {"id": "42", "username": "tester"},
        "guild": {"id": "100"},
        "permissions": 8 if discord_admin else 0,
        "has_discord_admin": discord_admin,
        "member_role_ids": roles or set(),
    }


async def _async_context(*, roles: set[int] | None = None, discord_admin: bool = False):
    return _context(roles=roles, discord_admin=discord_admin)


@pytest.mark.asyncio
async def test_activity_access_returns_403_before_role_sync(activity_db, monkeypatch):
    service = ActivityAccessService()

    async def fetch_context(*_):
        return await _async_context(discord_admin=True)

    monkeypatch.setattr(service, "fetch_user_context", fetch_context)

    with pytest.raises(HTTPException) as exc:
        await service.fetch_user_and_access_state("token", "100")

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "roles_not_synced"
    assert exc.value.detail["can_sync_roles"] is True


@pytest.mark.asyncio
async def test_activity_access_grants_default_modules_after_role_sync(activity_db, monkeypatch):
    service = ActivityAccessService()

    async def fetch_context(*_):
        return await _async_context(roles={10})

    monkeypatch.setattr(service, "fetch_user_context", fetch_context)

    await service._ensure_builtin_access_roles(100)
    await activity_db.execute(
        """
        INSERT INTO activity_synced_roles (guild_id, role_id, name, permissions)
        VALUES (?, ?, ?, ?)
        """,
        (100, 10, "Member", 0),
    )
    await activity_db.commit()

    _, access = await service.fetch_user_and_access_state("token", "100")

    assert access["access_level"] == "ordinary"
    assert set(access["available_modules"]) == {"dashboard", "health"}
    assert access["permissions"]["logs"] == "disabled"


@pytest.mark.asyncio
async def test_activity_access_uses_assignment_for_administrator(activity_db, monkeypatch):
    service = ActivityAccessService()

    async def fetch_context(*_):
        return await _async_context(roles={99})

    monkeypatch.setattr(service, "fetch_user_context", fetch_context)

    await service._ensure_builtin_access_roles(100)
    admin_role = await activity_db.fetch_one(
        "SELECT id FROM activity_access_roles WHERE guild_id = ? AND slug = ?",
        (100, "administrator"),
    )
    await activity_db.execute(
        """
        INSERT INTO activity_synced_roles (guild_id, role_id, name, permissions, is_admin)
        VALUES (?, ?, ?, ?, ?)
        """,
        (100, 99, "Admins", 8, 1),
    )
    await activity_db.execute(
        """
        INSERT INTO activity_synced_role_assignments (guild_id, discord_role_id, access_role_id)
        VALUES (?, ?, ?)
        """,
        (100, 99, admin_role["id"]),
    )
    await activity_db.commit()

    _, access = await service.fetch_user_and_access_state("token", "100")

    assert access["is_admin"] is True
    assert access["permissions"]["bot-settings"] == "manage"
    assert access["permissions"]["access"] == "manage"


@pytest.mark.asyncio
async def test_rbac_service_rejects_administrator_permission_update(activity_db, monkeypatch):
    access_service = ActivityAccessService()
    await access_service._ensure_builtin_access_roles(100)
    admin_role = await activity_db.fetch_one(
        "SELECT id FROM activity_access_roles WHERE guild_id = ? AND slug = ?",
        (100, "administrator"),
    )

    service = ActivityRbacService()

    async def ensure_admin(*_):
        return {"id": "42", "username": "admin"}

    monkeypatch.setattr(service._access_service, "ensure_admin", ensure_admin)

    with pytest.raises(HTTPException) as exc:
        await service.update_access_role_modules(
            100, admin_role["id"], {"logs": "disabled"}, "token"
        )

    assert exc.value.status_code == 400
    assert "immutable" in exc.value.detail


@pytest.mark.asyncio
async def test_rbac_service_deletes_custom_access_role(activity_db, monkeypatch):
    access_service = ActivityAccessService()
    await access_service._ensure_builtin_access_roles(100)

    service = ActivityRbacService()

    async def ensure_admin(*_):
        return {"id": "42", "username": "admin"}

    monkeypatch.setattr(service._access_service, "ensure_admin", ensure_admin)
    role = await service.create_access_role(100, "QA", "token")

    result = await service.delete_access_role(100, role.id, "token")
    deleted = await activity_db.fetch_one(
        "SELECT * FROM activity_access_roles WHERE id = ?", (role.id,)
    )

    assert result["deleted"] is True
    assert deleted is None


@pytest.mark.asyncio
async def test_rbac_service_serializes_postgres_synced_datetime(activity_db, monkeypatch):
    service = ActivityRbacService()

    async def no_assignments(*_):
        return []

    monkeypatch.setattr(service, "_get_assignments", no_assignments)

    role = await service._to_synced_role(
        {
            "role_id": 10,
            "guild_id": 100,
            "name": "Admins",
            "color": 0,
            "position": 1,
            "permissions": 8,
            "is_admin": True,
            "managed": False,
            "mentionable": True,
            "synced_at": datetime(2026, 6, 28, 15, 16, 31),
        }
    )

    assert role.synced_at == "2026-06-28 15:16:31"


@pytest.mark.asyncio
async def test_rbac_role_sync_persists_flags_as_bigints(monkeypatch):
    service = ActivityRbacService()
    captured_parameters: list[tuple[object, ...]] = []

    async def execute(_query, parameters):
        captured_parameters.append(parameters)

    async def commit():
        return None

    async def ensure_discord_administrator(*_):
        return {"id": "42", "username": "admin"}

    async def list_roles(_guild_id):
        return [
            SimpleNamespace(
                id="99",
                name="Administrators",
                color=0,
                position=1,
                permissions=8,
                managed=False,
                mentionable=True,
            ),
        ]

    async def no_access_role(*_):
        return None

    async def no_audit(**_):
        return None

    async def no_synced_roles(*_):
        return []

    monkeypatch.setattr(
        rbac_service_module,
        "get_db",
        lambda: SimpleNamespace(execute=execute, commit=commit),
    )
    monkeypatch.setattr(
        service._access_service,
        "ensure_discord_administrator",
        ensure_discord_administrator,
    )
    monkeypatch.setattr(service._discord, "list_roles", list_roles)
    monkeypatch.setattr(service, "_get_access_role_by_slug", no_access_role)
    monkeypatch.setattr(service._audit_service, "log_action", no_audit)
    monkeypatch.setattr(service, "list_synced_roles", no_synced_roles)

    await service.sync_roles(100, "token")

    role_parameters = captured_parameters[0]
    assert role_parameters[6:] == (1, 0, 1)
    assert all(type(value) is int for value in role_parameters[6:])


@pytest.mark.asyncio
async def test_repository_role_sync_uses_column_name_and_bigint_flag(monkeypatch):
    repository = RoleRepository(SimpleNamespace())
    captured: list[tuple[str, tuple[object, ...]]] = []

    async def execute(query, parameters):
        captured.append((query, parameters))

    async def commit():
        return None

    async def ensure_builtin_roles(_guild_id):
        return None

    monkeypatch.setattr(repository, "execute", execute)
    monkeypatch.setattr(repository, "commit", commit)
    monkeypatch.setattr(repository, "_ensure_activity_builtin_roles", ensure_builtin_roles)

    await repository.sync_activity_roles_from_discord(
        100,
        [
            {
                "id": "99",
                "name": "Administrators",
                "permissions": 8,
                "managed": False,
                "mentionable": True,
            }
        ],
    )

    query, parameters = captured[0]
    assert "is_admin," in query
    assert "int(is_admin)" not in query
    assert parameters[6:] == (1, 0, 1)


@pytest.mark.asyncio
async def test_dev_blog_rejects_more_than_ten_drafts(activity_db, monkeypatch):
    service = DevBlogService()

    async def ensure_developer(*_):
        return {"id": "42", "username": "dev"}, {"is_developer": True}

    monkeypatch.setattr(
        service._access_service, "ensure_developer_or_admin", ensure_developer
    )
    await activity_db.execute(
        "INSERT INTO server_channel_purposes (guild_id, purpose, channel_id) VALUES (?, ?, ?)",
        (100, "dev_blog", 555),
    )
    for index in range(10):
        await activity_db.execute(
            """
            INSERT INTO dev_blog_posts (guild_id, channel_id, author_id, title, payload_json, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
            """,
            (100, 555, 42, f"Draft {index}", "{}"),
        )
    await activity_db.commit()

    payload = DevBlogPostPayload(
        guild_id=100,
        title="Draft 11",
        embeds=[DevBlogEmbedPayload(description="body")],
        status="draft",
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_post(payload, "token")

    assert exc.value.status_code == 400
    assert "draft limit" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_voice_room_user_can_only_manage_own_room(activity_db, monkeypatch):
    service = VoiceRoomService()

    async def ensure_voice(*_):
        return {"id": "42", "username": "owner"}, {
            "access_level": "ordinary",
            "is_admin": False,
        }

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_voice)

    async def bot_request(*_, **__):
        return {"id": "700", "name": "Owner room", "permission_overwrites": []}

    monkeypatch.setattr(service._discord, "bot_request", bot_request)
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (700, 100, 42, "Owner room"),
    )
    await activity_db.execute(
        "INSERT INTO voice_rooms (channel_id, guild_id, owner_id, name) VALUES (?, ?, ?, ?)",
        (701, 100, 99, "Other room"),
    )
    await activity_db.commit()

    result = await service.update_room(
        700, VoiceRoomUpdatePayload(guild_id=100, locked=False), "token"
    )
    with pytest.raises(HTTPException) as exc:
        await service.update_room(
            701, VoiceRoomUpdatePayload(guild_id=100, locked=False), "token"
        )

    assert result["updated"] is True
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_welcome_test_requires_configured_welcome_channel(activity_db, monkeypatch):
    service = ActivityWelcomeService()

    async def ensure_welcome(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_welcome)

    with pytest.raises(HTTPException) as exc:
        await service.send_test_message(100, "token")

    assert exc.value.status_code == 400
    assert "welcome" in exc.value.detail
