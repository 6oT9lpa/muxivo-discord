from datetime import datetime
from typing import Any, Optional

from activity.server.dependencies import get_db
from activity.server.schemas.rbac import (
    ActivityAuditEvent,
    ActivityAuditPage,
    ActivityDashboardMetric,
    ActivityDashboardResponse,
)
from activity.server.services.access_service import ActivityAccessService
from activity.server.services.discord_service import DiscordService
from activity.server.utils.rbac import MODULE_ORDER
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class ActivityDashboardService:
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()
        self._discord = DiscordService()

    async def get_dashboard(
        self, guild_id: int, access_token: str
    ) -> ActivityDashboardResponse:
        logger.info("Loading Activity dashboard guild_id=%s", guild_id)
        _, access = await self._access_service.ensure_module_access(
            access_token, str(guild_id), "dashboard"
        )
        metrics = await self._build_metrics(guild_id, access)
        # Audit details often contain moderation reasons and member identifiers.
        # They belong to the Logs permission, not to the public dashboard tab.
        audit = (
            await self._query_audit_events(guild_id, limit=5, offset=0)
            if self._access_service._permission_allows(
                access.get("permissions", {}).get("logs", "disabled"), "view"
            )
            else ActivityAuditPage(items=[], total=0, limit=5, offset=0)
        )
        return ActivityDashboardResponse(metrics=metrics, audit=audit.items)

    async def get_control_summary(self, guild_id: int) -> dict[str, int | None]:
        """Return the non-sensitive dashboard subset for the signed Console API.

        Console authorization is evaluated before this method is reached.  This
        deliberately omits Activity-role-dependent module counts and all audit
        rows, which may expose user identifiers or moderation details.
        """
        logger.info("Loading Console dashboard summary guild_id=%s", guild_id)
        return {
            "messages_today": await self._count_messages_today(guild_id),
            "ai_flagged_today": await self._count_messages_today(
                guild_id, flagged=True
            ),
            "creator_sources": await self._count_creator_sources(guild_id),
            "bot_latency_ms": await self._discord.measure_latency(),
        }

    async def list_audit_events(
        self,
        guild_id: int,
        access_token: str,
        *,
        query: str = "",
        actor: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> ActivityAuditPage:
        logger.info(
            "Listing Activity audit events guild_id=%s limit=%s offset=%s",
            guild_id,
            limit,
            offset,
        )
        await self._access_service.ensure_module_access(
            access_token, str(guild_id), "logs"
        )
        return await self._query_audit_events(
            guild_id,
            query=query,
            actor=actor,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    async def _build_metrics(
        self, guild_id: int, access: dict[str, Any]
    ) -> ActivityDashboardMetric:
        modules_ready = len(access.get("available_modules", []))
        modules_total = len(MODULE_ORDER)
        permissions = access.get("permissions", {})
        can_view_stats = self._access_service._permission_allows(
            permissions.get("server-stats", "disabled"), "view"
        )
        can_view_creator_sources = self._access_service._permission_allows(
            permissions.get("creator-alerts", "disabled"), "view"
        )
        ai_checks_today = (
            await self._count_messages_today(guild_id) if can_view_stats else 0
        )
        ai_flagged_today = (
            await self._count_messages_today(guild_id, flagged=True)
            if can_view_stats
            else 0
        )
        creator_sources = (
            await self._count_creator_sources(guild_id)
            if can_view_creator_sources
            else 0
        )
        return ActivityDashboardMetric(
            modules_ready=modules_ready,
            modules_total=modules_total,
            ai_checks_today=ai_checks_today,
            ai_flagged_today=ai_flagged_today,
            creator_sources=creator_sources,
            bot_latency_ms=await self._discord.measure_latency(),
        )

    async def _count_messages_today(
        self, guild_id: int, flagged: Optional[bool] = None
    ) -> int:
        # Dashboard must stay available even while optional analytics tables are absent.
        clauses = ["guild_id = ?", "DATE(timestamp) = CURRENT_DATE"]
        params: list[Any] = [guild_id]
        if flagged is not None:
            clauses.append("ai_flagged = ?")
            params.append(1 if flagged else 0)
        try:
            row = await get_db().fetch_one(
                f"SELECT COUNT(*) AS total FROM messages WHERE {' AND '.join(clauses)}",
                tuple(params),
            )
            return int(row["total"] if row else 0)
        except Exception as exc:
            logger.warning(
                "Dashboard message metric unavailable guild_id=%s flagged=%s error=%s",
                guild_id,
                flagged,
                exc,
            )
            return 0

    async def _count_creator_sources(self, guild_id: int) -> int:
        try:
            row = await get_db().fetch_one(
                "SELECT COUNT(*) AS total FROM creator_alert_subscriptions WHERE guild_id = ?",
                (guild_id,),
            )
            return int(row["total"] if row else 0)
        except Exception as exc:
            logger.warning(
                "Dashboard creator metric unavailable guild_id=%s error=%s",
                guild_id,
                exc,
            )
            return 0

    async def _query_audit_events(
        self,
        guild_id: int,
        *,
        query: str = "",
        actor: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int,
        offset: int,
    ) -> ActivityAuditPage:
        clauses = ["guild_id = ?"]
        params: list[Any] = [guild_id]

        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(event_type LIKE ? OR details LIKE ? OR target_name LIKE ?)"
            )
            params.extend([like, like, like])
        if actor.strip():
            like = f"%{actor.strip()}%"
            clauses.append("(actor_name LIKE ? OR CAST(actor_id AS TEXT) LIKE ?)")
            params.extend([like, like])
        if date_from.strip():
            clauses.append("created_at >= ?")
            params.append(date_from.strip())
        if date_to.strip():
            clauses.append("created_at <= ?")
            params.append(date_to.strip())

        where_sql = " AND ".join(clauses)
        try:
            total_row = await get_db().fetch_one(
                f"SELECT COUNT(*) AS total FROM guild_event_logs WHERE {where_sql}",
                tuple(params),
            )
            rows = await get_db().fetch_all(
                f"""
                SELECT id, guild_id, actor_id, actor_name, target_id, target_name, event_type, details, created_at
                FROM guild_event_logs
                WHERE {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            )
        except Exception as exc:
            logger.warning(
                "Dashboard audit stream unavailable guild_id=%s error=%s", guild_id, exc
            )
            total_row = {"total": 0}
            rows = []
        return ActivityAuditPage(
            items=[self._to_audit_event(row) for row in rows],
            total=int(total_row["total"] if total_row else 0),
            limit=limit,
            offset=offset,
        )

    def _to_audit_event(self, row: dict[str, Any]) -> ActivityAuditEvent:
        return ActivityAuditEvent(
            id=row["id"],
            guild_id=row["guild_id"],
            actor_id=row.get("actor_id"),
            actor_name=row.get("actor_name"),
            target_id=row.get("target_id"),
            target_name=row.get("target_name"),
            event_type=row["event_type"],
            details=row.get("details"),
            created_at=self._format_datetime(row.get("created_at")),
        )

    def _format_datetime(self, value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="seconds")
        if value is None:
            logger.warning("Dashboard audit row has empty created_at")
            return ""
        return str(value)
