from typing import Any, Optional

from activity.server.dependencies import get_db
from activity.server.services.access_service import ActivityAccessService
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class LogsService:
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()

    async def list_logs(
        self,
        guild_id: int,
        source: str,
        event_type: Optional[str],
        query: str,
        limit: int,
        access_token: str,
    ) -> dict[str, list[dict[str, Any]]]:
        logger.info("Listing Activity logs guild_id=%s source=%s event_type=%s limit=%s", guild_id, source, event_type, limit)
        await self._access_service.ensure_module_access(access_token, str(guild_id), "logs")
        normalized_source = source.strip().lower() or "all"
        return {
            "messages": [] if normalized_source in {"audit", "activity", "moderator", "welcome", "channel", "ai"} else await self._query_message_logs(guild_id, event_type, query, limit),
            "audit": [] if normalized_source == "messages" else await self._query_audit_logs(guild_id, normalized_source, event_type, query, limit),
        }

    async def list_actors(self, guild_id: int, access_token: str) -> list[dict[str, str]]:
        logger.info("Listing Activity log actors guild_id=%s", guild_id)
        await self._access_service.ensure_module_access(access_token, str(guild_id), "logs")
        actors: dict[str, str] = {}
        for row in await self._safe_fetch_all(
            """
            SELECT actor_id AS id, actor_name AS name FROM guild_event_logs
            WHERE guild_id = ? AND actor_id IS NOT NULL
            UNION
            SELECT author_id AS id, author_name AS name FROM message_logs
            WHERE guild_id = ? AND author_id IS NOT NULL
            ORDER BY name
            """,
            (guild_id, guild_id),
            "log actor list",
        ):
            actor_id = str(row.get("id") or "")
            if actor_id:
                actors[actor_id] = str(row.get("name") or actor_id)
        return [{"id": actor_id, "name": name} for actor_id, name in actors.items()]

    async def _query_message_logs(
        self,
        guild_id: int,
        event_type: Optional[str],
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["guild_id = ?"]
        params: list[Any] = [guild_id]
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if query.strip():
            clauses.append("(content LIKE ? OR author_name LIKE ?)")
            like = f"%{query.strip()}%"
            params.extend([like, like])
        params.append(limit)
        return await self._safe_fetch_all(
            f"""
            SELECT * FROM message_logs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
            "message logs",
        )

    async def _query_audit_logs(
        self,
        guild_id: int,
        source: str,
        event_type: Optional[str],
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = ["guild_id = ?"]
        params: list[Any] = [guild_id]
        if source == "ai":
            return await self._query_ai_moderation_logs(guild_id, event_type, query, limit)

        source_prefixes = {
            "moderator": ["moderation_", "punishment_", "auto_moderation_"],
            "welcome": ["welcome_", "member_"],
            "channel": ["channel_"],
            "activity": ["activity_"],
        }
        prefixes = source_prefixes.get(source, [])
        if prefixes:
            clauses.append("(" + " OR ".join("event_type LIKE ?" for _ in prefixes) + ")")
            params.extend(f"{prefix}%" for prefix in prefixes)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if query.strip():
            clauses.append("(details LIKE ? OR actor_name LIKE ? OR target_name LIKE ?)")
            like = f"%{query.strip()}%"
            params.extend([like, like, like])
        params.append(limit)
        audit_rows = await self._safe_fetch_all(
            f"""
            SELECT * FROM guild_event_logs
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
            "audit logs",
        )
        if source != "all":
            return audit_rows

        ai_rows = await self._query_ai_moderation_logs(guild_id, event_type, query, limit)
        return sorted(
            [*audit_rows, *ai_rows],
            key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")),
            reverse=True,
        )[:limit]

    async def _query_ai_moderation_logs(
        self,
        guild_id: int,
        event_type: Optional[str],
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Expose stored classifier decisions through the shared Activity log feed."""
        if event_type and event_type != "ai_moderation_decision":
            return []

        clauses = ["event.guild_id = ?"]
        params: list[Any] = [guild_id]
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(event.primary_label LIKE ? OR event.decision_action LIKE ? OR "
                "COALESCE(event.proposed_action, '') LIKE ? OR CAST(event.user_id AS TEXT) LIKE ? OR "
                "EXISTS (SELECT 1 FROM message_logs message WHERE message.guild_id = event.guild_id "
                "AND message.message_id = event.message_id AND message.content LIKE ?))"
            )
            params.extend([like, like, like, like, like])
        params.append(limit)

        rows = await self._safe_fetch_all(
            f"""
            SELECT event.*, (
                SELECT message.content FROM message_logs message
                WHERE message.guild_id = event.guild_id AND message.message_id = event.message_id
                ORDER BY message.created_at DESC, message.id DESC
                LIMIT 1
            ) AS message_content
            FROM ai_moderation_events event
            WHERE {' AND '.join(clauses)}
            ORDER BY event.created_at DESC, event.id DESC
            LIMIT ?
            """,
            tuple(params),
            "AI moderation logs",
        )
        return [self._to_ai_moderation_log(row) for row in rows]

    @staticmethod
    def _to_ai_moderation_log(row: dict[str, Any]) -> dict[str, Any]:
        labels = [str(label) for label in row.get("labels_json") or () if str(label)]
        decision = str(row.get("decision_action") or "LOG")
        proposed_action = str(row.get("proposed_action") or "")
        fields = [
            {"name": "Member", "value": f"<@{row['user_id']}>", "inline": True},
            {"name": "Risk", "value": f"{float(row.get('risk_score') or 0):.0f} / 100", "inline": True},
            {"name": "Decision", "value": decision, "inline": True},
            {"name": "Classification", "value": ", ".join(labels) or str(row.get("primary_label") or "SAFE"), "inline": False},
            {"name": "Message", "value": str(row.get("message_content") or f"[Message ID: {row['message_id']}]"), "inline": False},
        ]
        if proposed_action and proposed_action != decision:
            fields.insert(3, {"name": "AI recommendation", "value": proposed_action, "inline": False})
        return {
            "id": f"ai-{row['id']}",
            "guild_id": row["guild_id"],
            "channel_id": row["channel_id"],
            "actor_id": None,
            "actor_name": "AI classifier",
            "target_id": row["user_id"],
            "target_name": None,
            "event_type": "ai_moderation_decision",
            "details": {
                "title": "AI classifier decision",
                "fields": fields,
                "footer": {"text": f"AI classifier • {str(row.get('status') or 'RECORDED').title()} • {int(row.get('latency_ms') or 0)} ms"},
                "color": "#8b5cf6",
            },
            "created_at": row["created_at"],
        }

    async def _safe_fetch_all(self, query: str, params: tuple[Any, ...], label: str) -> list[dict[str, Any]]:
        try:
            return await get_db().fetch_all(query, params)
        except Exception as exc:
            logger.warning("Activity %s unavailable error=%s", label, exc)
            return []
