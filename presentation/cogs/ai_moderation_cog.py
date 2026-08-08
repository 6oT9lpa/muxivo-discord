from __future__ import annotations

from datetime import datetime, timedelta

import disnake
from disnake.ext import commands, tasks

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from application.services.ai_moderation_queue import AiModerationQueue
from application.services.ai_moderation_policy_enforcer import AiModerationPolicyEnforcer
from application.services.ai_moderation_settings_service import AiModerationSettingsService
from application.services.channel_service import ChannelService
from application.services.discord_message_content import DiscordMessageContentNormalizer
from application.services.discord_media_attachment_normalizer import DiscordMediaAttachmentNormalizer
from application.services.flood_enforcement_coordinator import FloodEnforcementCoordinator
from application.services.user_moderation_context_builder import UserModerationContextBuilder
from core.domain.channel_purpose import ChannelPurpose
from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy
from core.domain.value_objects import PunishmentType
from core.interfaces.repositories.punishment_repository_interface import PunishmentRepositoryInterface
from core.interfaces.repositories.ai_moderation_repository_interface import AiModerationRepositoryInterface
from infrastructure.logging import get_logger
from presentation.embeds.base import EmbedBuilder, DEFAULT_COLORS

logger = get_logger(__name__)


class AiModerationCog(commands.Cog):
    """Connect Discord messages, moderation decisions and audit logging."""
    _HIGH_IMPACT_ACTIONS = frozenset({"TIMEOUT", "KICK", "BAN"})
    _ACTION_PERMISSION = {
        "TIMEOUT": "moderate_members",
        "KICK": "kick_members",
        "BAN": "ban_members",
    }

    def __init__(self, bot: commands.Bot, settings_service: AiModerationSettingsService, channel_service: ChannelService, queue: AiModerationQueue, context_builder: UserModerationContextBuilder, punishment_repository: PunishmentRepositoryInterface, ai_repository: AiModerationRepositoryInterface | None = None) -> None:
        self._bot = bot
        self._settings_service = settings_service
        self._channel_service = channel_service
        self._queue = queue
        self._context_builder = context_builder
        self._punishment_repository = punishment_repository
        self._ai_repository = ai_repository
        self._content_normalizer = DiscordMessageContentNormalizer()
        self._policy_enforcer = AiModerationPolicyEnforcer()
        self._flood_coordinator = FloodEnforcementCoordinator()

    async def cog_load(self) -> None:
        await self._queue.start()
        if self._ai_repository is not None:
            self.restore_administrator_roles.start()
        logger.info("AI moderation cog loaded")

    async def shutdown(self) -> None:
        self.restore_administrator_roles.cancel()
        await self._queue.stop()

    @tasks.loop(minutes=1)
    async def restore_administrator_roles(self) -> None:
        """Return saved administrator roles only after the related timeout ends."""
        if self._ai_repository is None:
            return
        for item in await self._ai_repository.list_due_role_restorations():
            guild = self._bot.get_guild(int(item["guild_id"]))
            if guild is None:
                continue
            member = guild.get_member(int(item["user_id"]))
            if member is None:
                continue
            raw_role_ids = item.get("role_ids_json", [])
            role_ids = tuple(int(role_id) for role_id in raw_role_ids) if isinstance(raw_role_ids, list) else ()
            await self._restore_roles(guild, member, role_ids, "AI moderation timeout ended")
            await self._ai_repository.mark_roles_restored(guild.id, member.id)

    @restore_administrator_roles.before_loop
    async def before_restore_administrator_roles(self) -> None:
        await self._bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message) -> None:
        if message.author.bot or message.guild is None or not isinstance(message.channel, (disnake.TextChannel, disnake.NewsChannel)):
            return
        if not await self._settings_service.is_enabled_for_channel(message.guild.id, message.channel.id):
            return
        request = await self._build_request(message, "CREATE")
        if request is None:
            return
        if not self._queue.submit(request):
            logger.warning("AI moderation queue rejected message guild_id=%s message_id=%s", message.guild.id, message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message) -> None:
        if after.author.bot or after.guild is None or not isinstance(after.channel, (disnake.TextChannel, disnake.NewsChannel)):
            return
        if not self._content_normalizer.changed(before, after):
            return
        request = await self._build_request(after, "UPDATE")
        if request is not None and not self._queue.submit(request):
            logger.warning("AI moderation queue rejected updated message guild_id=%s message_id=%s", after.guild.id, after.id)

    async def _build_request(self, message: disnake.Message, event_type: str) -> AiModerationRequest | None:
        """Build a bounded request with author history and reply context.

        Recent messages are supplied for flood detection only; the AI service
        still evaluates the current message content as a separate signal.
        """
        if message.guild is None or not isinstance(message.channel, (disnake.TextChannel, disnake.NewsChannel)):
            return None
        if not await self._settings_service.is_enabled_for_channel(message.guild.id, message.channel.id):
            return None
        policy = AiModerationGuildPolicy.model_validate(await self._settings_service.get_policy(message.guild.id))
        user_context = await self._context_builder.build(
            message.author,
            message.guild.id,
            message.author.id,
            policy.context_window_days,
            policy.escalation_half_life_days,
        )
        recent_messages, recent_timestamps = await self._recent_author_messages(message)
        metadata = await self._reply_context(message)
        metadata["ocr_max_gif_frames"] = policy.ocr_max_gif_frames
        metadata["ocr_process_empty_result"] = policy.ocr_process_empty_result
        metadata["ocr_failure_mode"] = policy.ocr_failure_mode
        media_attachments = self._media_attachments(message) if policy.ocr_enabled else ()
        metadata["discord_attachment_count"] = len(message.attachments)
        return AiModerationRequest(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            user_id=message.author.id,
            author_role_ids=tuple(role.id for role in getattr(message.author, "roles", ()) if role != message.guild.default_role),
            author_is_bot=message.author.bot,
            message_id=message.id,
            raw_text=message.content,
            created_at=message.created_at,
            author_created_at=user_context.account_created_at,
            member_joined_at=user_context.joined_guild_at,
            reply_to_message_id=message.reference.message_id if message.reference else None,
            mention_count=len(message.mentions),
            role_mention_count=len(message.role_mentions),
            channel_mention_count=len(message.channel_mentions),
            has_attachments=bool(media_attachments),
            attachment_count=len(media_attachments),
            attachments=media_attachments,
            recent_messages=recent_messages,
            recent_message_timestamps=recent_timestamps,
            metadata=metadata,
            model_min_risk_by_label={label: rule.model_min_risk for label, rule in policy.labels.items()},
            event_type=event_type,
            user_context=user_context,
        )

    @classmethod
    def _media_attachments(cls, message: disnake.Message):
        return DiscordMediaAttachmentNormalizer.normalize_many(message.attachments)

    @commands.slash_command(name="set", description="AI moderation settings")
    @commands.has_permissions(administrator=True)
    async def set_group(self, _: disnake.ApplicationCommandInteraction) -> None:
        return None

    @set_group.sub_command(name="ai-channel", description="Enable AI moderation for a text channel")
    async def set_ai_channel(self, ctx: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel) -> None:
        await self._settings_service.add_channel(ctx.guild_id, channel.id)
        await ctx.response.send_message(f"AI moderation enabled for {channel.mention}.", ephemeral=True)

    @commands.slash_command(name="list", description="AI moderation lists")
    @commands.has_permissions(administrator=True)
    async def list_group(self, _: disnake.ApplicationCommandInteraction) -> None:
        return None

    @list_group.sub_command(name="ai-channel", description="List AI-moderated channels")
    async def list_ai_channel(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        channel_ids = await self._settings_service.list_channels(ctx.guild_id)
        channels = [f"<#{channel_id}>" for channel_id in channel_ids]
        await ctx.response.send_message("\n".join(channels) if channels else "No AI-moderated channels configured.", ephemeral=True)

    @commands.slash_command(name="ai-policy", description="Configure guild AI moderation preferences")
    @commands.has_permissions(administrator=True)
    async def ai_policy(self, _: disnake.ApplicationCommandInteraction) -> None:
        return None

    @ai_policy.sub_command(name="label", description="Set risk and action limits for a moderation label")
    async def set_label_policy(self, ctx: disnake.ApplicationCommandInteraction, label: str, min_action: str = "LOG", max_action: str = "BAN", risk_threshold: float = 0) -> None:
        policy = await self._settings_service.get_policy(ctx.guild_id)
        labels = dict(policy.get("labels", {}))
        labels[label.upper()] = {"min_action": min_action.upper(), "max_action": max_action.upper(), "risk_threshold": max(0.0, min(100.0, risk_threshold))}
        policy["labels"] = labels
        await self._save_policy(ctx, policy, f"Policy saved for {label.upper()}.")

    @ai_policy.sub_command(name="blacklist", description="Set comma-separated blacklist words")
    async def set_blacklist(self, ctx: disnake.ApplicationCommandInteraction, words: str) -> None:
        policy = await self._settings_service.get_policy(ctx.guild_id)
        policy["blacklist_words"] = tuple(item.strip().lower() for item in words.split(",") if item.strip())[:200]
        await self._save_policy(ctx, policy, "Blacklist preferences saved.")

    @ai_policy.sub_command(name="domains", description="Set comma-separated allowed domains")
    async def set_domains(self, ctx: disnake.ApplicationCommandInteraction, domains: str) -> None:
        policy = await self._settings_service.get_policy(ctx.guild_id)
        policy["allowed_domains"] = tuple(item.strip().lower() for item in domains.split(",") if item.strip())[:200]
        await self._save_policy(ctx, policy, "Domain preferences saved.")

    @ai_policy.sub_command(name="context-window", description="Set the user-history window in days")
    async def set_context_window(self, ctx: disnake.ApplicationCommandInteraction, days: int) -> None:
        policy = await self._settings_service.get_policy(ctx.guild_id)
        policy["context_window_days"] = days
        await self._save_policy(ctx, policy, "Moderation context window saved.")

    @ai_policy.sub_command(name="repeat-offender", description="Escalate AI moderation after repeated punishments")
    async def set_repeat_offender_policy(self, ctx: disnake.ApplicationCommandInteraction, threshold: int, action: str = "TIMEOUT") -> None:
        policy = await self._settings_service.get_policy(ctx.guild_id)
        policy["repeat_offender_threshold"] = threshold
        policy["repeat_offender_action"] = action.upper()
        await self._save_policy(ctx, policy, "Repeat-offender policy saved.")

    async def handle_decision(self, request: AiModerationRequest, decision: AiModerationDecision) -> None:
        """Enforce a queued recommendation and persist its execution outcome."""
        policy = await self._settings_service.get_policy(request.guild_id)
        try:
            decision = self._policy_enforcer.apply(request, decision, policy)
        except ValueError:
            logger.exception("Invalid guild AI moderation policy guild_id=%s", request.guild_id)
        guild = self._bot.get_guild(request.guild_id)
        if guild is None:
            return
        member = guild.get_member(request.user_id)
        channel = guild.get_channel(request.channel_id)
        message = channel.get_partial_message(request.message_id) if isinstance(channel, (disnake.TextChannel, disnake.NewsChannel)) else None
        decision = self._limit_to_executable_member_action(guild, member, decision)
        if self._is_flood_timeout(decision) and not decision.dry_run:
            is_primary_flood_incident = self._flood_coordinator.begin_or_join(
                request.guild_id,
                request.user_id,
                request.message_id,
                self._timeout_duration(decision),
                datetime.now(),
            )
            if not is_primary_flood_incident:
                await self._coalesce_flood_message(guild, member, message, request, decision)
                return
        status = "SUCCESS"
        try:
            for action in decision.execution_plan:
                try:
                    await self._execute_action(
                        guild,
                        member,
                        message,
                        action,
                        decision.dry_run,
                        decision,
                        request,
                    )
                except disnake.Forbidden:
                    if decision.dry_run or action not in self._HIGH_IMPACT_ACTIONS:
                        raise
                    if self._is_flood_timeout(decision):
                        self._flood_coordinator.abort(request.guild_id, request.user_id)
                    logger.warning(
                        "Discord rejected AI moderation member action; falling back to warning "
                        "guild_id=%s user_id=%s message_id=%s action=%s",
                        request.guild_id,
                        request.user_id,
                        request.message_id,
                        action,
                    )
                    decision = self._warning_fallback(decision)
                    await self._execute_action(
                        guild,
                        member,
                        message,
                        "WARN",
                        False,
                        decision,
                        request,
                    )
                    await self._record_ai_punishment(request, "WARN", False)
                    break
                await self._record_ai_punishment(request, action, decision.dry_run)
            # The AI API tracks a single decision, while Discord enforcement
            # may need multiple technical steps (for example DELETE → TIMEOUT).
            # Report the terminal technical action after every step succeeds.
            # DELETE_WARN is an aggregate Discord outcome; Core records WARN.
            await self._queue.report_action(
                decision.event_id,
                self._result_action(decision),
                "DRY_RUN" if decision.dry_run else "SUCCESS",
                decision.dry_run,
            )
        except Exception:
            status = "FAILED"
            if self._is_flood_timeout(decision):
                self._flood_coordinator.abort(request.guild_id, request.user_id)
            logger.exception("AI moderation action failed guild_id=%s message_id=%s", request.guild_id, request.message_id)
            try:
                await self._queue.report_action(
                    decision.event_id,
                    self._result_action(decision),
                    "FAILED",
                    decision.dry_run,
                )
            except Exception:
                logger.exception(
                    "Could not report terminal AI moderation failure guild_id=%s message_id=%s",
                    request.guild_id,
                    request.message_id,
                )
        # Audit persistence must never suppress the moderator-facing decision log.
        # The log is the immediate feedback loop for Shadow Mode and is useful even
        # when a transient database problem prevents dataset collection.
        try:
            await self._settings_service.record_event(
                request.guild_id, request.channel_id, request.message_id, request.user_id,
                decision.risk_score, decision.action, decision.proposed_action,
                decision.primary_label, decision.labels, decision.confidence,
                decision.latency_ms, status,
            )
        except Exception:
            logger.exception(
                "Could not persist AI moderation event guild_id=%s message_id=%s",
                request.guild_id,
                request.message_id,
            )
        if decision.action == "REVIEW":
            # A review correction is operationally more valuable than an event
            # telemetry row, so a temporary dataset failure must not lose it.
            try:
                await self._settings_service.create_review_item(
                    request.guild_id, request.channel_id, request.message_id, request.user_id,
                    request.raw_text, decision.risk_score, decision.severity, decision.proposed_action or decision.action, decision.labels,
                )
            except Exception:
                logger.exception("Could not enqueue AI review item guild_id=%s message_id=%s", request.guild_id, request.message_id)
        await self._send_log(guild, request, decision, status)

    @staticmethod
    def _result_action(decision: AiModerationDecision) -> str:
        """Map aggregate Discord outcomes to the Core action-result contract."""
        return "WARN" if decision.action == "DELETE_WARN" else decision.action

    @staticmethod
    def _is_flood_timeout(decision: AiModerationDecision) -> bool:
        return decision.action == "TIMEOUT" and "FLOOD" in {label.upper() for label in decision.labels}

    def _limit_to_executable_member_action(
        self,
        guild: disnake.Guild,
        member: disnake.Member | None,
        decision: AiModerationDecision,
    ) -> AiModerationDecision:
        """Downgrade an unavailable member restriction without hiding its proposal."""
        if (
            decision.dry_run
            or decision.action not in self._HIGH_IMPACT_ACTIONS
            or self._can_execute_member_action(guild, member, decision.action)
        ):
            return decision
        logger.info(
            "AI moderation member action is unavailable; using delete and warning "
            "guild_id=%s user_id=%s message_id=%s action=%s",
            decision.guild_id,
            decision.user_id,
            decision.message_id,
            decision.action,
        )
        return self._warning_fallback(decision)

    def _can_execute_member_action(
        self,
        guild: disnake.Guild,
        member: disnake.Member | None,
        action: str,
    ) -> bool:
        if member is None or action not in self._HIGH_IMPACT_ACTIONS:
            return False
        if member.id == getattr(guild, "owner_id", None):
            return False

        bot_member = getattr(guild, "me", None)
        if bot_member is None or member.id == getattr(bot_member, "id", None):
            return False
        bot_top_role = getattr(bot_member, "top_role", None)
        member_top_role = getattr(member, "top_role", None)
        bot_top_position = getattr(bot_top_role, "position", None)
        member_top_position = getattr(member_top_role, "position", None)
        if (
            bot_top_position is None
            or member_top_position is None
            or member_top_position >= bot_top_position
        ):
            return False

        permissions = getattr(bot_member, "guild_permissions", None)
        permission_name = self._ACTION_PERMISSION[action]
        if permissions is None or not getattr(permissions, permission_name, False):
            return False

        if action == "TIMEOUT" and getattr(
            getattr(member, "guild_permissions", None),
            "administrator",
            False,
        ):
            administrator_roles = tuple(
                role
                for role in getattr(member, "roles", ())
                if not role.is_default() and role.permissions.administrator
            )
            if not administrator_roles or any(
                role.managed or role.position >= bot_top_position
                for role in administrator_roles
            ):
                return False
        return True

    @staticmethod
    def _warning_fallback(decision: AiModerationDecision) -> AiModerationDecision:
        return decision.model_copy(
            update={
                "action": "DELETE_WARN",
                "proposed_action": decision.proposed_action or decision.action,
                "execution_plan": ("DELETE", "WARN"),
            }
        )

    async def _coalesce_flood_message(
        self,
        guild: disnake.Guild,
        member: disnake.Member | None,
        message: disnake.PartialMessage | None,
        request: AiModerationRequest,
        decision: AiModerationDecision,
    ) -> None:
        """Delete a later flood message without duplicating timeout or its log."""
        try:
            await self._execute_action(guild, member, message, "DELETE", decision.dry_run, decision, request)
            await self._queue.report_action(
                decision.event_id,
                decision.action,
                "DRY_RUN" if decision.dry_run else "SUCCESS",
                decision.dry_run,
            )
            await self._settings_service.record_event(
                request.guild_id, request.channel_id, request.message_id, request.user_id,
                decision.risk_score, decision.action, decision.proposed_action,
                decision.primary_label, decision.labels, decision.confidence,
                decision.latency_ms, "COALESCED",
            )
        except Exception:
            logger.exception("Could not coalesce flood message guild_id=%s message_id=%s", request.guild_id, request.message_id)

    async def _save_policy(self, ctx: disnake.ApplicationCommandInteraction, policy: dict[str, object], success_message: str) -> None:
        try:
            validated_policy = self._policy_enforcer.validate(policy)
        except ValueError as exc:
            await ctx.response.send_message(f"Invalid policy: {exc}", ephemeral=True)
            return
        await self._settings_service.save_policy(ctx.guild_id, validated_policy)
        await ctx.response.send_message(success_message, ephemeral=True)

    async def _execute_action(self, guild: disnake.Guild, member: disnake.Member | None, message: disnake.PartialMessage | None, action: str, dry_run: bool, decision: AiModerationDecision, request: AiModerationRequest) -> None:
        if dry_run or action in {"IGNORE", "LOG", "REVIEW"}:
            return
        if action in {"DELETE", "DELETE_WARN"} and message is not None:
            # disnake only accepts an audit-log reason for bulk deletion; the
            # single-message endpoint rejects it. Calling without it lets the
            # configured Manage Messages permission perform the deletion.
            logging_cog = self._bot.get_cog("LoggingCog")
            if logging_cog is not None:
                logging_cog.register_bot_message_deletion(message.id)
            await message.delete()
        if action in {"WARN", "DELETE_WARN"} and member is not None:
            await self._send_warning_dm(member, guild, request, decision, action)
        elif action == "TIMEOUT" and member is not None:
            duration = self._timeout_duration(decision)
            removed_role_ids = await self._remove_administrator_roles(member, "AI moderation timeout")
            try:
                await member.timeout(duration=duration, reason="AI moderation policy")
                if removed_role_ids and self._ai_repository is not None:
                    await self._ai_repository.schedule_role_restoration(
                        guild.id,
                        member.id,
                        removed_role_ids,
                        datetime.now() + duration,
                    )
            except Exception:
                # Never leave an administrator stripped if Discord rejects the
                # timeout or the restoration record cannot be persisted.
                await self._restore_roles(guild, member, removed_role_ids, "AI moderation timeout rollback")
                raise
        elif action == "KICK" and member is not None:
            await member.kick(reason="AI moderation policy")
        elif action == "BAN" and member is not None:
            await guild.ban(member, reason="AI moderation policy")

    async def _remove_administrator_roles(self, member: disnake.Member, reason: str) -> tuple[int, ...]:
        """Remove only manageable Administrator roles and return their IDs."""
        bot_member = member.guild.me
        if bot_member is None:
            return ()
        roles = tuple(
            role
            for role in member.roles
            if not role.is_default()
            and not role.managed
            and role.permissions.administrator
            and role.position < bot_member.top_role.position
        )
        if not roles:
            return ()
        await member.remove_roles(*roles, reason=reason)
        return tuple(role.id for role in roles)

    async def _restore_roles(self, guild: disnake.Guild, member: disnake.Member, role_ids: tuple[int, ...], reason: str) -> None:
        """Restore only still-manageable roles recorded before the timeout."""
        bot_member = guild.me
        if bot_member is None or not role_ids:
            return
        roles = tuple(
            role
            for role_id in role_ids
            if (role := guild.get_role(role_id)) is not None
            and not role.is_default()
            and not role.managed
            and role.position < bot_member.top_role.position
            and role not in member.roles
        )
        if roles:
            await member.add_roles(*roles, reason=reason)

    async def _send_warning_dm(self, member: disnake.Member, guild: disnake.Guild, request: AiModerationRequest, decision: AiModerationDecision, action: str) -> None:
        """Send a self-contained moderation notice that remains useful after deletion."""
        _, action_title, _ = self._action_presentation(action)
        labels = ", ".join(label.replace("_", " ").title() for label in (decision.labels or (decision.primary_label,)))
        occurred_at = f"<t:{int(request.created_at.timestamp())}:F>"
        embed = (
            EmbedBuilder(color=DEFAULT_COLORS["warn"])
            .set_title("Предупреждение AI-модератора")
            .set_description("Одно из ваших сообщений нарушило правила сервера.")
            .add_field("Сервер", guild.name, inline=False)
            .add_field("Канал", f"<#{request.channel_id}>", inline=True)
            .add_field("Когда", occurred_at, inline=True)
            .add_field("Причина", labels, inline=False)
            .add_field("Действие", action_title, inline=False)
            .build()
        )
        try:
            await member.send(embed=embed)
        except (disnake.Forbidden, disnake.HTTPException):
            # Closed DMs must not roll back an otherwise successful deletion.
            logger.info("Could not send AI moderation DM user_id=%s guild_id=%s", member.id, guild.id)

    @staticmethod
    def _timeout_duration(decision: AiModerationDecision) -> timedelta:
        """Keep timeout proportional to the engine's severity and aggregate risk."""
        severity, risk = decision.severity, decision.risk_score
        if severity >= 5 or risk >= 90:
            return timedelta(hours=24)
        if severity >= 4 or risk >= 75:
            return timedelta(hours=6)
        if severity >= 3 or risk >= 60:
            return timedelta(hours=1)
        if severity >= 2 or risk >= 40:
            return timedelta(minutes=20)
        return timedelta(minutes=10)

    async def _record_ai_punishment(self, request: AiModerationRequest, action: str, dry_run: bool) -> None:
        if dry_run:
            return
        punishment_type = {
            "WARN": PunishmentType.WARN,
            "TIMEOUT": PunishmentType.TIMEOUT,
            "KICK": PunishmentType.KICK,
            "BAN": PunishmentType.BAN,
        }.get(action)
        if punishment_type is None:
            return
        await self._punishment_repository.add_punishment(
            request.user_id,
            0,
            punishment_type,
            "AI moderation policy",
            guild_id=request.guild_id,
            message_id=request.message_id,
            source="MUXIVO_CORE",
        )

    async def _send_log(self, guild: disnake.Guild, request: AiModerationRequest, decision: AiModerationDecision, status: str) -> None:
        content = request.raw_text.strip() or ("[attachment]" if request.has_attachments else "[empty message]")
        content = content[:1_000]
        jump_url = f"https://discord.com/channels/{guild.id}/{request.channel_id}/{request.message_id}"
        action_icon, action_title, color = self._action_presentation(decision.action)
        proposed = decision.proposed_action or decision.action
        _, proposed_title, _ = self._action_presentation(proposed)
        labels = ", ".join(label.replace("_", " ").title() for label in (decision.labels or (decision.primary_label,)))
        execution_context = "Test mode — no Discord actions executed" if decision.dry_run else "Decision recorded"
        reply_text = request.metadata.get("reply_context_text")
        reply_author_id = request.metadata.get("reply_context_author_id")
        # Match the compact visual hierarchy used by the rest of Muxivo Discord's
        # activity logs: the first row answers who/what/how severe, with only
        # the extra context that a moderator needs beneath it.
        builder = (
            EmbedBuilder(color=color)
            .set_title("AI moderation decision")
            .add_field("Member", f"<@{decision.user_id}>", inline=True)
            .add_field("Risk", f"{decision.risk_score:.0f} / 100", inline=True)
            .add_field("Decision", f"{action_icon} {action_title}", inline=True)
        )
        if proposed != decision.action:
            builder.add_field("AI recommendation", proposed_title, inline=False)
        is_reply = isinstance(reply_text, str) and bool(reply_text)
        if is_reply:
            # Field values have a 1,024-character Discord limit. Reply context
            # is capped at 1,000 characters at collection time, so the full
            # original message fits here with quote formatting intact. Keeping
            # author and ID in the value makes the message/answer pair easier
            # to scan than an overloaded field heading.
            author = f"<@{reply_author_id}>" if reply_author_id else "unknown member"
            author_id = str(reply_author_id) if reply_author_id else "unknown"
            message_header = f"**Being answered:** {author} | ID: `{author_id}`"
            max_primary_text = 1_024 - len(message_header) - len("\n> ")
            builder.add_field("Message", f"{message_header}\n> {reply_text[:max_primary_text]}", inline=False)
            if len(reply_text) > max_primary_text:
                # Discord limits each embed field to 1,024 characters. A
                # second field preserves the complete referenced message.
                builder.add_field("Message (continued)", f"> {reply_text[max_primary_text:]}", inline=False)
        elif request.reply_to_message_id:
            original_url = f"https://discord.com/channels/{guild.id}/{request.channel_id}/{request.reply_to_message_id}"
            builder.add_field("Message", f"[Open message being answered]({original_url})", inline=False)
        embed = (
            builder
            .add_field("Answer" if is_reply else "Message", f"> {content}", inline=False)
            .add_field("Classification", labels, inline=False)
            .set_footer(f"{execution_context} • {status.title()} • {decision.latency_ms} ms")
            .build()
        )
        for purpose, channel in await self._resolve_log_channels(guild, request.channel_id):
            try:
                await channel.send(embed=embed)
            except (disnake.Forbidden, disnake.HTTPException):
                logger.exception(
                    "Could not send AI moderation embed guild_id=%s channel_id=%s purpose=%s",
                    guild.id,
                    channel.id,
                    purpose,
                )
                continue
            if purpose != ChannelPurpose.AI_MODERATION_LOG.value:
                logger.warning(
                    "AI moderation log used fallback destination guild_id=%s channel_id=%s purpose=%s",
                    guild.id,
                    channel.id,
                    purpose,
                )
            return
        logger.error("AI moderation embed could not be delivered guild_id=%s message_id=%s", guild.id, request.message_id)

    async def _resolve_log_channels(
        self,
        guild: disnake.Guild,
        source_channel_id: int,
    ) -> list[tuple[str, disnake.TextChannel | disnake.NewsChannel]]:
        """Resolve ordered, unique destinations so a classifier response never disappears silently."""
        candidates: list[tuple[str, int]] = []
        for purpose in (
            ChannelPurpose.AI_MODERATION_LOG,
            ChannelPurpose.MOD_LOG,
            ChannelPurpose.MESSAGE_LOG,
        ):
            channel_id = await self._channel_service.get_purpose_channel(guild.id, purpose)
            if channel_id:
                candidates.append((purpose.value, channel_id))
        candidates.append(("source_channel", source_channel_id))

        resolved: list[tuple[str, disnake.TextChannel | disnake.NewsChannel]] = []
        seen_channel_ids: set[int] = set()
        for purpose, channel_id in candidates:
            if channel_id in seen_channel_ids:
                continue
            seen_channel_ids.add(channel_id)
            channel = guild.get_channel(channel_id)
            if channel is None:
                fetch_channel = getattr(guild, "fetch_channel", None)
                if fetch_channel is None:
                    logger.warning(
                        "AI moderation log destination is absent from the guild cache guild_id=%s channel_id=%s purpose=%s",
                        guild.id,
                        channel_id,
                        purpose,
                    )
                    continue
                try:
                    channel = await fetch_channel(channel_id)
                except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
                    logger.warning(
                        "AI moderation log destination is unavailable guild_id=%s channel_id=%s purpose=%s",
                        guild.id,
                        channel_id,
                        purpose,
                    )
                    continue
            if isinstance(channel, (disnake.TextChannel, disnake.NewsChannel)):
                resolved.append((purpose, channel))
            else:
                logger.warning(
                    "AI moderation log destination is not text-based guild_id=%s channel_id=%s purpose=%s",
                    guild.id,
                    channel_id,
                    purpose,
                )
        return resolved

    @staticmethod
    def _action_presentation(action: str) -> tuple[str, str, int]:
        """Translate internal actions into compact, moderator-friendly status copy."""
        presentation = {
            "IGNORE": ("✅", "No action needed", DEFAULT_COLORS["success"]),
            "LOG": ("📝", "Logged for visibility", DEFAULT_COLORS["info"]),
            "REVIEW": ("🔎", "Review requested", DEFAULT_COLORS["warn"]),
            "WARN": ("⚠️", "Warning issued", DEFAULT_COLORS["warn"]),
            "DELETE": ("🗑️", "Message deleted", DEFAULT_COLORS["moderation"]),
            "DELETE_WARN": ("🛡️", "Message deleted and warning issued", DEFAULT_COLORS["moderation"]),
            "TIMEOUT": ("⏳", "Member timed out", DEFAULT_COLORS["moderation"]),
            "KICK": ("👢", "Member removed", DEFAULT_COLORS["moderation"]),
            "BAN": ("🔨", "Member banned", DEFAULT_COLORS["moderation"]),
        }
        return presentation.get(action.upper(), ("ℹ️", action.replace("_", " ").title(), DEFAULT_COLORS["info"]))

    async def _recent_author_messages(self, message: disnake.Message) -> tuple[tuple[str, ...], tuple[datetime, ...]]:
        """Return only the author's preceding messages: this is the flood context, not classifier text."""
        recent: list[str] = []
        timestamps: list[datetime] = []
        try:
            async for item in message.channel.history(limit=20, before=message, oldest_first=False):
                if item.author.id != message.author.id:
                    continue
                recent.append(item.content[:1_000])
                timestamps.append(item.created_at)
        except (disnake.Forbidden, disnake.HTTPException):
            logger.debug("Could not load message history message_id=%s", message.id)
        return tuple(recent), tuple(timestamps)

    async def _reply_context(self, message: disnake.Message) -> dict[str, object]:
        if message.reference is None or message.reference.message_id is None:
            return {}
        try:
            referenced = message.reference.resolved
            if not isinstance(referenced, disnake.Message):
                referenced = await message.channel.fetch_message(message.reference.message_id)
            return {
                "reply_context_message_id": str(referenced.id),
                "reply_context_author_id": str(referenced.author.id),
                "reply_context_text": referenced.content[:1_000],
            }
        except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
            return {
                "reply_context_message_id": str(message.reference.message_id),
                "reply_context_unavailable": True,
            }
