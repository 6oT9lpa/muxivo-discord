from datetime import datetime
from typing import Mapping

from psycopg.types.json import Jsonb

from core.interfaces.repositories.ai_moderation_repository_interface import AiModerationRepositoryInterface
from infrastructure.database.repositories.base import BaseRepository


class AiModerationRepository(BaseRepository, AiModerationRepositoryInterface):
    async def add_channel(self, guild_id: int, channel_id: int) -> None:
        await self.execute(
            "INSERT INTO ai_moderation_channels (guild_id, channel_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (guild_id, channel_id),
        )

    async def remove_channel(self, guild_id: int, channel_id: int) -> bool:
        result = await self.execute(
            "DELETE FROM ai_moderation_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        )
        return bool(result.rowcount)

    async def list_channels(self, guild_id: int) -> list[int]:
        rows = await self.fetch_all(
            "SELECT channel_id FROM ai_moderation_channels WHERE guild_id = ? ORDER BY channel_id",
            (guild_id,),
        )
        return [int(row["channel_id"]) for row in rows]

    async def get_policy(self, guild_id: int) -> dict[str, object]:
        row = await self.fetch_one("SELECT policy_json FROM ai_moderation_settings WHERE guild_id = ?", (guild_id,))
        payload = row["policy_json"] if row else {}
        return dict(payload) if isinstance(payload, dict) else {}

    async def save_policy(self, guild_id: int, policy: Mapping[str, object]) -> None:
        await self.execute(
            """
            INSERT INTO ai_moderation_settings (guild_id, policy_json)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET policy_json = excluded.policy_json, updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, Jsonb(dict(policy))),
        )

    async def save_event(self, guild_id: int, channel_id: int, message_id: int, user_id: int, risk_score: float, action: str, proposed_action: str | None, primary_label: str, labels: tuple[str, ...], confidence: float, latency_ms: int, status: str) -> None:
        await self.execute(
            """
            INSERT INTO ai_moderation_events (guild_id, channel_id, message_id, user_id, risk_score, decision_action, proposed_action, primary_label, labels_json, confidence, latency_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, message_id) DO UPDATE SET risk_score = excluded.risk_score, decision_action = excluded.decision_action,
              proposed_action = excluded.proposed_action, primary_label = excluded.primary_label, labels_json = excluded.labels_json,
              confidence = excluded.confidence, latency_ms = excluded.latency_ms, status = excluded.status
            """,
            (guild_id, channel_id, message_id, user_id, risk_score, action, proposed_action, primary_label, Jsonb(list(labels)), confidence, latency_ms, status),
        )

    async def create_review_item(self, guild_id: int, channel_id: int, message_id: int, user_id: int, message_text: str, risk_score: float, severity: int, action: str, labels: tuple[str, ...]) -> None:
        await self.execute(
            """INSERT INTO ai_moderation_review_items (guild_id, channel_id, message_id, user_id, message_text, risk_score, severity, action, labels_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (guild_id, message_id) DO NOTHING""",
            (guild_id, channel_id, message_id, user_id, message_text[:8000], risk_score, severity, action, Jsonb(list(labels))),
        )

    async def count_ai_deleted_messages(self, guild_id: int, user_id: int, since: datetime) -> int:
        row = await self.fetch_one(
            """SELECT COUNT(*) AS count FROM ai_moderation_events
               WHERE guild_id = ? AND user_id = ? AND created_at >= ?
                 AND decision_action IN ('DELETE', 'DELETE_WARN') AND status = 'SUCCESS'""",
            (guild_id, user_id, since),
        )
        return int(row["count"]) if row else 0

    async def schedule_role_restoration(self, guild_id: int, user_id: int, role_ids: tuple[int, ...], restore_at: datetime) -> None:
        """Persist administrator roles that may be safely returned after timeout."""
        await self.execute(
            """
            INSERT INTO ai_moderation_role_restorations (guild_id, user_id, role_ids_json, restore_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                role_ids_json = excluded.role_ids_json,
                restore_at = GREATEST(ai_moderation_role_restorations.restore_at, excluded.restore_at),
                restored_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, Jsonb(list(role_ids)), restore_at),
        )

    async def list_due_role_restorations(self) -> list[dict[str, object]]:
        return await self.fetch_all(
            """
            SELECT guild_id, user_id, role_ids_json
            FROM ai_moderation_role_restorations
            WHERE restored_at IS NULL AND restore_at <= CURRENT_TIMESTAMP
            ORDER BY restore_at ASC
            """
        )

    async def mark_roles_restored(self, guild_id: int, user_id: int) -> None:
        await self.execute(
            """
            UPDATE ai_moderation_role_restorations
            SET restored_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ? AND user_id = ? AND restored_at IS NULL
            """,
            (guild_id, user_id),
        )
