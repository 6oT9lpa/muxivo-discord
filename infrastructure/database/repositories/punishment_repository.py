from datetime import datetime
from typing import List, Optional, Dict, Any

from core.domain.value_objects import PunishmentType

from application.dto.moderation_dto import PunishmentDTO
from core.interfaces.repositories import PunishmentRepositoryInterface
from infrastructure.database.connection import DatabaseManager
from infrastructure.database.repositories.base import BaseRepository
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class PunishmentRepository(PunishmentRepositoryInterface, BaseRepository):
    _TABLE_NAME = "punishments"
    _ALLOWED_COLUMNS = {
        "guild_id", "user_id", "moderator_id", "type", "reason", "duration_seconds",
        "expires_at", "is_active", "created_at", "retention_until",
    }

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)

    async def add(self, dto: PunishmentDTO) -> int:
        data = dto.to_db()
        row_id = await self.insert(data)
        logger.debug("Inserted punishment id=%s type=%s", row_id, dto.type)
        return row_id

    async def get(self, punishment_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetch_one("SELECT * FROM punishments WHERE id = ?", (punishment_id,))

    async def get_active(
        self,
        guild_id: int,
        user_id: int,
        punishment_type: str,
    ) -> Optional[Dict[str, Any]]:
        return await self.fetch_one(
            """
            SELECT * FROM punishments
            WHERE guild_id = ? AND user_id = ? AND type = ? AND is_active = 1
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (guild_id, user_id, punishment_type),
        )

    async def list_active(
        self,
        guild_id: int,
        punishment_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if punishment_type:
            query = """
                SELECT * FROM punishments
                WHERE guild_id = ? AND type = ? AND is_active = 1
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """
            params = (guild_id, punishment_type, limit)
        else:
            query = """
                SELECT * FROM punishments
                WHERE guild_id = ? AND is_active = 1
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """
            params = (guild_id, limit)
        return await self.fetch_all(query, params)

    async def list_for_user(
        self,
        guild_id: int,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return await self.fetch_all(
            """
            SELECT * FROM punishments
            WHERE guild_id = ? AND user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (guild_id, user_id, limit),
        )

    async def deactivate(
        self,
        punishment_id: int,
    ) -> bool:
        cursor = await self.execute(
            "UPDATE punishments SET is_active = 0 WHERE id = ? AND is_active = 1",
            (punishment_id,),
        )
        await self.commit()
        return cursor.rowcount > 0

    async def cleanup_expired(
        self,
        cutoff_iso: str,
    ) -> int:
        cursor = await self.execute(
            "DELETE FROM punishments WHERE retention_until IS NOT NULL AND retention_until < ?",
            (cutoff_iso,),
        )
        await self.commit()
        return cursor.rowcount

    async def add_punishment(
        self,
        user_id: int,
        moderator_id: int,
        punishment_type: PunishmentType,
        reason: str,
        *,
        guild_id: int,
        duration: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        message_id: Optional[int] = None,
        source: str = "HUMAN",
    ) -> int:
        if guild_id <= 0:
            raise ValueError("guild_id must be positive")
        normalized_source = source.upper()
        if normalized_source not in {"MUXIVO_CORE", "HUMAN", "EXTERNAL"}:
            raise ValueError("source must be MUXIVO_CORE, HUMAN or EXTERNAL")
        await self.execute_write(
            """
            INSERT INTO punishments (guild_id, user_id, moderator_id, type, reason, duration_seconds, expires_at, message_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, message_id, type, source) DO NOTHING
            """,
            (guild_id, user_id, moderator_id, punishment_type.value, reason, duration, expires_at, message_id, normalized_source),
        )
        message_clause = "message_id = ?" if message_id is not None else "message_id IS NULL"
        params = (guild_id, message_id, punishment_type.value, normalized_source) if message_id is not None else (guild_id, punishment_type.value, normalized_source)
        row = await self.fetch_one(
            f"SELECT id FROM punishments WHERE guild_id = ? AND {message_clause} AND type = ? AND source = ? ORDER BY id DESC LIMIT 1",
            params,
        )
        if row is None:
            raise RuntimeError("punishment record was not persisted")
        return int(row["id"])

    async def get_active_punishments(
        self,
        user_id: int,
        punishment_type: Optional[PunishmentType] = None,
    ) -> List[Dict[str, Any]]:
        if punishment_type is None:
            return await self.fetch_all(
                """
                SELECT * FROM punishments
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
        return await self.fetch_all(
            """
            SELECT * FROM punishments
            WHERE user_id = ? AND type = ? AND is_active = 1
            ORDER BY created_at DESC, id DESC
            """,
            (user_id, punishment_type.value),
        )

    async def get_punishment_history(
        self,
        user_id: int,
        limit: int = 50,
        *,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        clauses = ["user_id = ?"]
        params: List[Any] = [user_id]
        if not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at >= CURRENT_TIMESTAMP)")
        params.append(limit)
        return await self.fetch_all(
            f"""
            SELECT * FROM punishments
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        )

    async def expire_punishment(
        self,
        punishment_id: int,
    ) -> bool:
        cursor = await self.execute(
            "UPDATE punishments SET is_active = 0 WHERE id = ? AND is_active = 1",
            (punishment_id,),
        )
        await self.commit()
        return cursor.rowcount > 0

    async def revoke_punishment(
        self,
        punishment_id: int,
        revoked_by: int,
    ) -> bool:
        cursor = await self.execute(
            """
            UPDATE punishments
            SET is_active = 0, reason = reason || ' | revoked_by=' || ?
            WHERE id = ? AND is_active = 1
            """,
            (str(revoked_by), punishment_id),
        )
        await self.commit()
        return cursor.rowcount > 0

    async def get_expired_punishments(self) -> List[Dict[str, Any]]:
        return await self.fetch_all(
            """
            SELECT * FROM punishments
            WHERE is_active = 1
              AND expires_at IS NOT NULL
              AND expires_at < CURRENT_TIMESTAMP
            ORDER BY expires_at ASC, id ASC
            """
        )

    async def get_warning_count(
        self,
        user_id: int,
        *,
        since: Optional[datetime] = None,
    ) -> int:
        clauses = ["user_id = ?", "type = 'warn'"]
        params: List[Any] = [user_id]
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since.isoformat(timespec="seconds"))
        params.append(1)
        row = await self.fetch_one(
            f"""
            SELECT COUNT(*) as count FROM punishments
            WHERE {' AND '.join(clauses)}
            LIMIT ?
            """,
            tuple(params),
        )
        return int(row["count"]) if row else 0

    async def get_all_active_mutes(self) -> List[Dict[str, Any]]:
        return await self.fetch_all(
            """
            SELECT * FROM punishments
            WHERE type IN ('mute', 'timeout') AND is_active = 1
            ORDER BY expires_at ASC, id ASC
            """
        )
