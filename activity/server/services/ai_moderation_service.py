"""Activity-facing read/write service for per-guild AI moderation settings."""

from datetime import datetime, timezone
from typing import Any

from activity.server.dependencies import get_db
from activity.server.services.access_service import ActivityAccessService
from activity.server.services.discord_service import DiscordService
from activity.server.schemas.ai_moderation_channels import AiModerationChannelsPayload
from activity.server.schemas.ai_moderation_policy import AiModerationPolicyPayload
from core.domain.default_ai_moderation_policy import default_ai_moderation_policy, merge_with_default_ai_moderation_policy
from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy
from application.dto.ai_moderation_request import AiModerationRequest
from application.dto.ai_moderation_decision import AiModerationDecision
from application.services.ai_moderation_policy_enforcer import AiModerationPolicyEnforcer
from infrastructure.ai.ai_moderator_api_client import AiModeratorApiClient
from infrastructure.config import get_config
from infrastructure.logging import get_logger
from psycopg.types.json import Jsonb
from fastapi import HTTPException

logger = get_logger(__name__)


class AiModerationService:
    """Authorize Activity requests and expose settings plus trusted metrics."""
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()
        self._discord_service = DiscordService()

    async def get_settings(self, guild_id: int, access_token: str) -> dict[str, Any]:
        logger.info("Loading AI moderation settings guild_id=%s", guild_id)
        await self._access_service.ensure_module_access(access_token, str(guild_id), "ai-moderator")
        channels = await get_db().fetch_all("SELECT channel_id FROM ai_moderation_channels WHERE guild_id = ? ORDER BY channel_id", (guild_id,))
        policy_row = await get_db().fetch_one("SELECT policy_json FROM ai_moderation_settings WHERE guild_id = ?", (guild_id,))
        log_row = await get_db().fetch_one("SELECT channel_id FROM server_channel_purposes WHERE guild_id = ? AND purpose = ?", (guild_id, "ai_moderation_log"))
        stored_policy = dict(policy_row["policy_json"]) if policy_row and isinstance(policy_row["policy_json"], dict) else None
        effective_policy, is_default_policy = self._effective_policy(stored_policy, guild_id)
        metrics_enabled = await self._metrics_enabled(guild_id)
        return {
            "guild_id": str(guild_id),
            "channels": [str(row["channel_id"]) for row in channels],
            "log_channel_id": str(log_row["channel_id"]) if log_row else None,
            "policy": effective_policy,
            "is_default_policy": is_default_policy,
            "available_channels": await self._discord_service.list_channels(str(guild_id), "moderation"),
            "metrics_enabled": metrics_enabled,
            "review_access": await self.can_access_review_queue(guild_id, access_token),
        }

    async def save_channels(self, payload: AiModerationChannelsPayload, access_token: str) -> dict[str, Any]:
        logger.info(
            "Saving AI moderation channel coverage guild_id=%s channel_count=%s",
            payload.guild_id,
            len(payload.channel_ids),
        )
        await self._access_service.ensure_module_access(access_token, str(payload.guild_id), "ai-moderator", "manage")
        requested_channel_ids = set(payload.channel_ids)
        channel_ids = await self._discord_service.filter_moderation_channel_ids(str(payload.guild_id), requested_channel_ids)
        dropped_channel_ids = sorted(requested_channel_ids - channel_ids)
        if dropped_channel_ids:
            logger.warning(
                "Dropped non-moderatable AI moderation channels guild_id=%s channel_ids=%s",
                payload.guild_id,
                dropped_channel_ids,
            )
        await get_db().execute("DELETE FROM ai_moderation_channels WHERE guild_id = ?", (payload.guild_id,))
        for channel_id in channel_ids:
            await get_db().execute("INSERT INTO ai_moderation_channels (guild_id, channel_id) VALUES (?, ?) ON CONFLICT DO NOTHING", (payload.guild_id, channel_id))
        await get_db().commit()
        logger.info("Saved AI moderation channel coverage guild_id=%s", payload.guild_id)
        return await self.get_settings(payload.guild_id, access_token)

    async def get_metrics(self, guild_id: int, access_token: str) -> dict[str, object]:
        """Return privacy-gated aggregate quality metrics, never message content."""
        await self._access_service.ensure_module_access(access_token, str(guild_id), "ai-moderator")
        if not await self._metrics_enabled(guild_id):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="AI moderation metrics require DM trust from the owner or trusted ADMIN")
        rows = await get_db().fetch_all("SELECT primary_label, labels_json, decision_action, proposed_action, confidence, latency_ms, created_at FROM ai_moderation_events WHERE guild_id = ? ORDER BY created_at DESC LIMIT 5000", (guild_id,))
        manual = await get_db().fetch_all("SELECT event.primary_label, label.label, event.created_at AS event_created_at, label.created_at AS label_created_at FROM ai_moderation_events event JOIN manual_labels label ON label.guild_id = event.guild_id AND label.message_id = event.message_id WHERE event.guild_id = ? AND label.status = 'ACTIVE'", (guild_id,))
        total = len(rows)
        would_delete = sum(row.get("proposed_action") in {"DELETE", "DELETE_WARN"} for row in rows)
        review_count = sum(row["decision_action"] == "REVIEW" for row in rows)
        average_latency = round(sum(int(row.get("latency_ms") or 0) for row in rows) / total) if total else 0
        noisy: dict[str, int] = {}
        for row in rows:
            for label in row.get("labels_json") or []:
                noisy[str(label)] = noisy.get(str(label), 0) + 1
        confused: dict[str, int] = {}
        safe_false_positives = 0
        correction_seconds: list[float] = []
        for row in manual:
            pair = f"{row['primary_label']} → {row['label']}"
            if row["primary_label"] != row["label"]:
                confused[pair] = confused.get(pair, 0) + 1
            if row["label"] == "SAFE" and row["primary_label"] != "SAFE":
                safe_false_positives += 1
            event_created_at, label_created_at = row.get("event_created_at"), row.get("label_created_at")
            if event_created_at and label_created_at and label_created_at >= event_created_at:
                correction_seconds.append((label_created_at - event_created_at).total_seconds())
        return {
            "total_messages": total,
            "would_delete": would_delete,
            "review_count": review_count,
            "average_latency_ms": average_latency,
            "safe_false_positive_rate": round(safe_false_positives / len(manual), 4) if manual else None,
            "confused_classes": self._top_counts(confused),
            "noisy_rules": self._top_counts(noisy),
            "moderator_correction_seconds": round(sum(correction_seconds) / len(correction_seconds)) if correction_seconds else None,
        }

    async def _metrics_enabled(self, guild_id: int) -> bool:
        return await get_db().fetch_one("SELECT 1 FROM ai_moderation_metrics_access WHERE guild_id = ?", (guild_id,)) is not None

    async def can_access_review_queue(self, guild_id: int, access_token: str) -> bool:
        """Review data is more sensitive than normal panel settings.

        Access therefore requires an explicitly trusted guild and a user appointed
        through Labeling (or the fixed service owner), independently of Activity RBAC.
        """
        try:
            context = await self._access_service.fetch_user_context(access_token, str(guild_id))
        except HTTPException:
            return False
        user_id = int(context["user"]["id"])
        trusted = await get_db().fetch_one("SELECT 1 FROM trusted_guilds WHERE guild_id = ?", (guild_id,))
        if trusted is None:
            return False
        if user_id == 762514681209946122:
            return True
        trusted_role = await get_db().fetch_one(
            "SELECT 1 FROM labeling_roles WHERE guild_id = ? AND user_id = ? AND role IN ('ADMIN', 'LABELER')",
            (guild_id, user_id),
        )
        return trusted_role is not None

    async def _ensure_review_access(self, guild_id: int, access_token: str) -> int:
        await self._access_service.ensure_module_access(access_token, str(guild_id), "ai-moderator")
        context = await self._access_service.fetch_user_context(access_token, str(guild_id))
        user_id = int(context["user"]["id"])
        if not await self.can_access_review_queue(guild_id, access_token):
            logger.warning("AI review queue access denied guild_id=%s user_id=%s", guild_id, user_id)
            raise HTTPException(status_code=403, detail="AI review queue requires a trusted guild and a Labeling ADMIN or LABELER role")
        return user_id

    async def list_review_items(self, guild_id: int, access_token: str, status: str, limit: int, offset: int) -> dict[str, object]:
        await self._ensure_review_access(guild_id, access_token)
        await self._backfill_review_items(guild_id)
        limit = max(1, min(limit, 50))
        offset = max(0, offset)
        rows = await get_db().fetch_all(
            """SELECT id, guild_id, channel_id, message_id, user_id, message_text, risk_score, severity, action,
                      labels_json, status, revision, created_at, updated_at, resolved_at, resolved_by
               FROM ai_moderation_review_items WHERE guild_id = ? AND status = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (guild_id, status, limit, offset),
        )
        total_row = await get_db().fetch_one(
            "SELECT COUNT(*) AS count FROM ai_moderation_review_items WHERE guild_id = ? AND status = ?", (guild_id, status)
        )
        return {"items": [self._review_item_payload(row) for row in rows], "total": int(total_row["count"] if total_row else 0), "limit": limit, "offset": offset}

    async def _backfill_review_items(self, guild_id: int) -> None:
        """Restore review work created before queue persistence was enabled.

        AI events are the durable source of truth for historic decisions.  Older
        REVIEW events were logged but never inserted into the editable queue,
        which made the panel appear empty despite real moderation activity.
        The unique ``(guild_id, message_id)`` constraint keeps this recovery
        idempotent for every queue refresh.
        """
        result = await get_db().execute(
            """
            INSERT INTO ai_moderation_review_items
                (guild_id, channel_id, message_id, user_id, message_text, risk_score, severity, action, labels_json)
            SELECT ai_event.guild_id,
                   ai_event.channel_id,
                   ai_event.message_id,
                   ai_event.user_id,
                   COALESCE(message_log.content, '[Message content is unavailable in retained logs]'),
                   ai_event.risk_score,
                   CASE
                     WHEN ai_event.risk_score >= 85 THEN 5
                     WHEN ai_event.risk_score >= 65 THEN 4
                     WHEN ai_event.risk_score >= 45 THEN 3
                     WHEN ai_event.risk_score >= 25 THEN 2
                     ELSE 1
                   END,
                   COALESCE(ai_event.proposed_action, ai_event.decision_action),
                   ai_event.labels_json
            FROM ai_moderation_events ai_event
            LEFT JOIN message_logs message_log
              ON message_log.guild_id = ai_event.guild_id
             AND message_log.channel_id = ai_event.channel_id
             AND message_log.message_id = ai_event.message_id
             AND message_log.author_id = ai_event.user_id
            WHERE ai_event.guild_id = ?
              AND (ai_event.decision_action = 'REVIEW' OR ai_event.proposed_action = 'REVIEW')
            ON CONFLICT (guild_id, message_id) DO NOTHING
            """,
            (guild_id,),
        )
        if result.rowcount:
            logger.info("Backfilled AI review items guild_id=%s count=%s", guild_id, result.rowcount)

    async def list_review_audit(self, guild_id: int, access_token: str, limit: int, offset: int) -> dict[str, object]:
        await self._ensure_review_access(guild_id, access_token)
        limit = max(1, min(limit, 50))
        offset = max(0, offset)
        rows = await get_db().fetch_all(
            """SELECT audit.id, audit.review_item_id, audit.actor_id, audit.action, audit.before_json, audit.after_json, audit.created_at,
                      item.message_id, item.user_id
               FROM ai_moderation_review_audit audit
               JOIN ai_moderation_review_items item ON item.id = audit.review_item_id
               WHERE audit.guild_id = ? ORDER BY audit.created_at DESC LIMIT ? OFFSET ?""",
            (guild_id, limit, offset),
        )
        total_row = await get_db().fetch_one("SELECT COUNT(*) AS count FROM ai_moderation_review_audit WHERE guild_id = ?", (guild_id,))
        return {"items": [dict(row) for row in rows], "total": int(total_row["count"] if total_row else 0), "limit": limit, "offset": offset}

    async def update_review_item(self, item_id: int, payload: Any, access_token: str) -> dict[str, object]:
        actor_id = await self._ensure_review_access(payload.guild_id, access_token)
        current = await get_db().fetch_one(
            "SELECT id, message_text, risk_score, severity, action, status, revision FROM ai_moderation_review_items WHERE id = ? AND guild_id = ?",
            (item_id, payload.guild_id),
        )
        if current is None:
            raise HTTPException(status_code=404, detail="Review item was not found")
        before = dict(current)
        result = await get_db().execute(
            """UPDATE ai_moderation_review_items SET message_text = ?, risk_score = ?, severity = ?, action = ?, status = ?,
                      revision = revision + 1, updated_at = CURRENT_TIMESTAMP,
                      resolved_at = CASE WHEN ? = 'RESOLVED' THEN CURRENT_TIMESTAMP ELSE NULL END,
                      resolved_by = CASE WHEN ? = 'RESOLVED' THEN ? ELSE NULL END
               WHERE id = ? AND guild_id = ? AND revision = ?""",
            (payload.message_text, payload.risk_score, payload.severity, payload.action.value, payload.status,
             payload.status, payload.status, actor_id, item_id, payload.guild_id, payload.revision),
        )
        if not result.rowcount:
            raise HTTPException(status_code=409, detail="Review item was changed by another moderator; reload it before saving")
        after = {"message_text": payload.message_text, "risk_score": payload.risk_score, "severity": payload.severity, "action": payload.action.value, "status": payload.status, "revision": payload.revision + 1}
        await get_db().execute(
            "INSERT INTO ai_moderation_review_audit (review_item_id, guild_id, actor_id, action, before_json, after_json) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, payload.guild_id, actor_id, "RESOLVED" if payload.status == "RESOLVED" else "UPDATED", Jsonb(before), Jsonb(after)),
        )
        logger.info("AI review item updated guild_id=%s item_id=%s actor_id=%s status=%s", payload.guild_id, item_id, actor_id, payload.status)
        refreshed = await get_db().fetch_one(
            "SELECT id, guild_id, channel_id, message_id, user_id, message_text, risk_score, severity, action, labels_json, status, revision, created_at, updated_at, resolved_at, resolved_by FROM ai_moderation_review_items WHERE id = ?", (item_id,)
        )
        return self._review_item_payload(refreshed) if refreshed else after

    @staticmethod
    def _review_item_payload(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["labels"] = list(item.pop("labels_json") or [])
        return item

    @staticmethod
    def _top_counts(values: dict[str, int]) -> list[dict[str, object]]:
        return [{"name": name, "count": count} for name, count in sorted(values.items(), key=lambda item: item[1], reverse=True)[:8]]

    def _effective_policy(self, stored_policy: dict[str, object] | None, guild_id: int) -> tuple[dict[str, object], bool]:
        if stored_policy is None:
            return default_ai_moderation_policy().model_dump(mode="json"), True
        try:
            policy = AiModerationGuildPolicy.model_validate(stored_policy)
            return merge_with_default_ai_moderation_policy(policy).model_dump(mode="json"), False
        except ValueError:
            logger.warning("Invalid stored AI moderation policy ignored guild_id=%s", guild_id)
            return default_ai_moderation_policy().model_dump(mode="json"), True

    async def save_policy(self, payload: AiModerationPolicyPayload, access_token: str) -> dict[str, Any]:
        logger.info(
            "Saving AI moderation policy guild_id=%s blacklist_count=%s domain_count=%s label_count=%s",
            payload.guild_id,
            len(payload.policy.blacklist_words),
            len(payload.policy.allowed_domains),
            len(payload.policy.labels),
        )
        await self._access_service.ensure_module_access(access_token, str(payload.guild_id), "ai-moderator", "manage")
        await get_db().execute(
            "INSERT INTO ai_moderation_settings (guild_id, policy_json) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET policy_json = excluded.policy_json, updated_at = CURRENT_TIMESTAMP",
            (payload.guild_id, Jsonb(payload.policy.model_dump(mode="json"))),
        )
        await get_db().commit()
        logger.info("Saved AI moderation policy guild_id=%s", payload.guild_id)
        return await self.get_settings(payload.guild_id, access_token)

    async def simulate(self, guild_id: int, message_text: str, access_token: str) -> dict[str, object]:
        """Return an inspectable decision while making no Discord or dataset mutation."""
        user, _ = await self._access_service.ensure_module_access(access_token, str(guild_id), "ai-moderator", "manage")
        policy = await self._load_policy(guild_id)
        if not policy.test_mode:
            raise HTTPException(status_code=409, detail="Enable AI moderator test mode before running a simulation")
        config = get_config()
        api_key = config.ai_moderator_internal_api_key
        if api_key is None:
            logger.error("AI simulation unavailable because internal key is not configured")
            raise HTTPException(status_code=503, detail="AI simulation is not configured")
        request = AiModerationRequest(
            guild_id=guild_id, channel_id=1, user_id=1, message_id=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            raw_text=message_text, created_at=datetime.now(timezone.utc), metadata={"simulation": True, "requested_by": str(user["id"])},
        )
        raw = await AiModeratorApiClient(
            config.ai_moderator_api_url, api_key.get_secret_value(), config.ai_moderator_request_timeout_seconds,
        ).simulate(request)
        model_decision = AiModerationDecision(
            event_id=1, user_id=request.user_id, guild_id=guild_id, message_id=request.message_id,
            risk_score=float(raw["risk_score"]), severity=int(raw.get("severity", 0)), confidence=float(raw.get("confidence", 0)),
            latency_ms=int(raw.get("latency_ms", 0)), action=str(raw["decision_action"]), proposed_action=str(raw["decision_action"]),
            primary_label=str(raw["primary_label"]), labels=tuple(str(label) for label in raw.get("labels", ())),
            rule_matches=tuple(str(rule) for rule in raw.get("rule_matches", ())), execution_plan=tuple(str(action) for action in raw.get("execution_plan", ())), dry_run=True,
        )
        # Test mode prevents live execution; use a temporary copy with the flag
        # disabled solely to disclose what the active policy would have selected.
        policy_for_preview = policy.model_copy(update={"test_mode": False})
        preview = AiModerationPolicyEnforcer().apply(request, model_decision, policy_for_preview)
        return {
            "simulation": True, "dataset_event_created": False,
            "primary_label": model_decision.primary_label, "labels": list(model_decision.labels),
            "risk_score": model_decision.risk_score, "severity": model_decision.severity, "confidence": model_decision.confidence,
            "model_action": model_decision.action, "policy_action": preview.action, "execution_plan": list(preview.execution_plan),
            "rule_matches": list(model_decision.rule_matches), "latency_ms": model_decision.latency_ms,
        }

    async def _load_policy(self, guild_id: int) -> AiModerationGuildPolicy:
        row = await get_db().fetch_one("SELECT policy_json FROM ai_moderation_settings WHERE guild_id = ?", (guild_id,))
        payload = dict(row["policy_json"]) if row and isinstance(row["policy_json"], dict) else {}
        return merge_with_default_ai_moderation_policy(AiModerationGuildPolicy.model_validate(payload))
