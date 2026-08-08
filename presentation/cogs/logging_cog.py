import asyncio
from collections import OrderedDict
from types import SimpleNamespace

import disnake
from disnake.ext import commands, tasks
from datetime import datetime, timezone
from typing import Optional

from application.services import AuditLogService, LoggingService, PunishmentEventRecorder
from application.services.discord_message_content import DiscordMessageContentNormalizer
from core.domain.value_objects import EventType
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class LoggingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, logging_service: LoggingService, audit_log_service: AuditLogService, punishment_recorder: PunishmentEventRecorder):
        self._logging_service = logging_service
        self._audit_log_service = audit_log_service
        self._punishment_recorder = punishment_recorder
        self._bot = bot
        self._content_normalizer = DiscordMessageContentNormalizer()
        # Gateway deletion events do not identify the actor. AI actions register
        # their message IDs before calling Discord so their logs stay accurate
        # without waiting for an eventually-consistent audit-log entry.
        self._bot_deleted_message_ids: set[int] = set()
        # Discord emits ``on_message_delete`` only for its own short-lived
        # message cache. Keep a bounded cache so raw deletion events can still
        # be logged when Discord has already evicted the original message.
        self._recent_messages: OrderedDict[int, disnake.Message] = OrderedDict()
        self._recent_message_limit = 5_000

    def register_bot_message_deletion(self, message_id: int) -> None:
        """Mark a deletion initiated by Muxivo Discord for the next gateway event."""
        self._bot_deleted_message_ids.add(message_id)

    def cog_load(self):
        self.cleanup_retention.change_interval(
            hours=self._logging_service.retention_cleanup_interval_hours
        )
        self.cleanup_retention.start()
        logger.info("LoggingCog initialized")

    def cog_unload(self):
        self.cleanup_retention.cancel()

    @tasks.loop(hours=6)
    async def cleanup_retention(self):
        try:
            await self._logging_service.cleanup_expired()
        except Exception as exc:
            logger.error("Retention cleanup failed: %s", exc)

    @cleanup_retention.before_loop
    async def before_cleanup(self):
        if self._bot:
            await self._bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        if not getattr(after, "guild", None) or not getattr(before, "guild", None) or before.author.bot:
            return
        if not self._content_normalizer.changed(before, after):
            return
        await self._logging_service.log_message_edit(before, after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: disnake.Message):
        self._recent_messages.pop(message.id, None)
        await self._log_deleted_message(message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: disnake.RawMessageDeleteEvent):
        """Log an uncached deletion using the bot's bounded message cache."""
        if payload.cached_message is not None:
            # The normal deletion listener receives cached messages.
            return
        message = self._recent_messages.pop(payload.message_id, None)
        if message is not None:
            await self._log_deleted_message(message)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        """Retain enough source data to log a later raw deletion event."""
        if not message.guild or message.author.bot:
            return
        self._recent_messages[message.id] = message
        self._recent_messages.move_to_end(message.id)
        while len(self._recent_messages) > self._recent_message_limit:
            self._recent_messages.popitem(last=False)

    async def _log_deleted_message(self, message: disnake.Message) -> None:
        """Resolve the actor where possible, then persist and send the log."""
        if not message.guild or message.author.bot:
            return

        deleted_by = self._bot.user if message.id in self._bot_deleted_message_ids else None
        self._bot_deleted_message_ids.discard(message.id)

        if deleted_by is None:
            deleted_by = await self._find_message_delete_actor(message)

        # Discord creates no audit-log record when someone deletes their own
        # message. In that case the message author is the only reliable actor.
        if deleted_by is None:
            deleted_by = message.author

        await self._logging_service.log_message_delete(
            message,
            deleted_by=deleted_by
        )

    async def _find_message_delete_actor(
        self,
        message: disnake.Message,
    ) -> Optional[disnake.Member | disnake.User]:
        """Resolve a moderator only from a matching, fresh audit-log entry.

        Discord sends the gateway deletion event before its audit-log entry is
        consistently visible. Retrying briefly prevents a moderator deletion
        from being incorrectly shown as a self-deletion by the message author.
        """
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(0.35)
            try:
                async for entry in message.guild.audit_logs(
                    limit=20,
                    action=disnake.AuditLogAction.message_delete,
                ):
                    target = getattr(entry, "target", None)
                    if target is None or target.id != message.author.id:
                        continue
                    if (datetime.now(timezone.utc) - entry.created_at).total_seconds() > 15:
                        continue

                    # The audit entry includes the affected channel. Matching
                    # it avoids assigning a nearby deletion from another
                    # channel by the same moderator to this message.
                    entry_channel = getattr(getattr(entry, "extra", None), "channel", None)
                    if entry_channel is not None and entry_channel.id != message.channel.id:
                        continue
                    return entry.user
            except Exception as exc:
                logger.warning("Failed to get audit log for message delete: %s", exc)
                return None
        return None

    @commands.Cog.listener()
    async def on_raw_bulk_delete(self, payload: disnake.RawBulkMessageDeleteEvent):
        guild = self._guild_from_id(payload.guild_id)
        if not guild:
            return
        channel = guild.get_channel(payload.channel_id)
        if not isinstance(channel, disnake.TextChannel):
            return
        deleted_by = None
        try:
            async for entry in guild.audit_logs(limit=5, action=disnake.AuditLogAction.message_delete):
                if entry.target and entry.target.id == payload.channel_id:
                    deleted_by = guild.get_member(entry.user.id)
                    break
        except Exception as e:
            logger.warning("Failed to get audit log for bulk delete: %s", e)

        await self._logging_service.log_bulk_delete([], channel, deleted_by=deleted_by)

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        if before.roles != after.roles:
            moderator = None
            try:
                async for entry in after.guild.audit_logs(limit=5, action=disnake.AuditLogAction.member_role_update):
                    if entry.target and entry.target.id == after.id:
                        moderator = after.guild.get_member(entry.user.id)
                        break
            except Exception:
                pass
            await self._logging_service.log_member_role_update(
                member=after,
                after_roles=list(after.roles),
                before_roles=list(before.roles),
                moderator=moderator,
            )

        changed = []
        if before.nick != after.nick:
            changed.append(f"nick: {before.nick} -> {after.nick}")
        if before.pending != after.pending:
            changed.append(f"pending: {before.pending} -> {after.pending}")
        if changed:
            await self._logging_service.log_member_event(
                EventType.MEMBER_UPDATE,
                after,
                extra_data={"changes": changed},
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: disnake.abc.GuildChannel):
        moderator = await self._get_audit_log_actor(
            channel.guild,
            disnake.AuditLogAction.channel_create,
            channel.id,
        )
        await self._logging_service.log_channel_create(channel, moderator)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: disnake.abc.GuildChannel):
        moderator = await self._get_audit_log_actor(
            channel.guild,
            disnake.AuditLogAction.channel_delete,
            channel.id,
        )
        await self._logging_service.log_channel_delete(channel, moderator)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: disnake.abc.GuildChannel, after: disnake.abc.GuildChannel):
        moderator = await self._get_audit_log_actor(
            after.guild,
            disnake.AuditLogAction.channel_update,
            after.id,
        )
        await self._logging_service.log_channel_update(before, after, moderator)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: disnake.Role):
        moderator = await self._get_audit_log_actor(
            role.guild,
            disnake.AuditLogAction.role_create,
            role.id,
        )
        await self._logging_service.log_role_create(role, moderator)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: disnake.Role):
        moderator = await self._get_audit_log_actor(
            role.guild,
            disnake.AuditLogAction.role_delete,
            role.id,
        )
        await self._logging_service.log_role_delete(role, moderator)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: disnake.Role, after: disnake.Role):
        moderator = await self._get_audit_log_actor(
            after.guild,
            disnake.AuditLogAction.role_update,
            after.id,
        )
        await self._logging_service.log_role_update(before, after, moderator)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: disnake.Member,
        before: disnake.VoiceState,
        after: disnake.VoiceState,
    ):
        if before.channel == after.channel:
            return

        await self._logging_service.log_voice_event(member, before, after)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: disnake.AuditLogEntry):
        if not self._bot:
            return

        action = entry.action
        logger.debug("Audit log entry: action=%s, user=%s, target=%s", action, entry.user, entry.target)

        if action == disnake.AuditLogAction.ban:
            target = entry.target
            moderator = entry.user
            if isinstance(target, (disnake.Member, disnake.User)):
                guild_id = entry.guild.id
                await self._logging_service.log_audit_ban(
                    moderator=moderator,
                    target=target,
                    reason=entry.reason or "Не указана",
                    guild_id=guild_id,
                )
                await self._record_ban(entry, target, moderator)

        elif action == disnake.AuditLogAction.unban:
            target = entry.target
            moderator = entry.user
            if isinstance(target, (disnake.Member, disnake.User)):
                guild_id = entry.guild.id
                await self._logging_service.log_audit_unban(
                    moderator=moderator,
                    target=target,
                    reason=entry.reason or "Не указана",
                    guild_id=guild_id,
                )

        elif action == disnake.AuditLogAction.kick:
            target = entry.target
            if isinstance(target, disnake.Member):
                await self._logging_service.log_audit_kick(target, entry.reason or "Не указана")

        elif action == disnake.AuditLogAction.member_update:
            if not entry.changes:
                return

            timeout_before = getattr(entry.changes.before, "communication_disabled_until", None)
            timeout_after = getattr(entry.changes.after, "communication_disabled_until", None)
            if timeout_before is None and timeout_after is None:
                return

            # disnake exposes AuditLogChanges as before/after diffs, rather
            # than an iterable collection of individual changes.
            for change in (
                SimpleNamespace(
                    key="communication_disabled_until",
                    before=timeout_before,
                    after=timeout_after,
                ),
            ):
                if change.key == "communication_disabled_until":
                    before_val = change.before
                    after_val = change.after
                    target = entry.target

                    if not isinstance(target, disnake.Member):
                        continue

                    now = datetime.now(timezone.utc)

                    if before_val is None and after_val is not None:
                        duration_seconds = int((after_val - now).total_seconds())
                        if duration_seconds < 0:
                            duration_seconds = 0
                        await self._logging_service.log_audit_mute(
                            target,
                            duration_seconds,
                            entry.reason or "Таймаут через аудит-лог",
                        )
                        await self._record_timeout(entry, target, duration_seconds, after_val)

                    elif before_val is not None and after_val is None:
                        await self._logging_service.log_audit_unmute(
                            target,
                            0,
                            entry.reason or "Снятие таймаута через аудит-лог",
                        )

                    elif before_val is not None and after_val is not None and before_val != after_val:
                        logger.debug("Timeout duration updated for %s: %s -> %s", target.id, before_val, after_val)
                    break 

    async def _record_ban(self, entry: disnake.AuditLogEntry, target: disnake.User, moderator: disnake.User | None) -> None:
        try:
            await self._punishment_recorder.record_ban(
                guild_id=entry.guild.id,
                user_id=target.id,
                moderator_id=getattr(moderator, "id", 0),
                audit_entry_id=entry.id,
                reason=entry.reason or "Не указана",
            )
        except Exception:
            logger.exception("Failed to record ban punishment guild_id=%s audit_entry_id=%s", entry.guild.id, entry.id)

    async def _record_timeout(self, entry: disnake.AuditLogEntry, target: disnake.Member, duration_seconds: int, expires_at: datetime) -> None:
        try:
            await self._punishment_recorder.record_timeout(
                guild_id=entry.guild.id,
                user_id=target.id,
                moderator_id=getattr(entry.user, "id", 0),
                audit_entry_id=entry.id,
                reason=entry.reason or "Таймаут через аудит-лог",
                duration_seconds=duration_seconds,
                expires_at=expires_at,
            )
        except Exception:
            logger.exception("Failed to record timeout punishment guild_id=%s audit_entry_id=%s", entry.guild.id, entry.id)

    async def _get_audit_log_actor(
        self,
        guild: disnake.Guild,
        action: disnake.AuditLogAction,
        target_id: int,
        limit: int = 10,
    ) -> disnake.Member:
        """Ищет в аудит-логе запись с указанным действием и целью, возвращает пользователя."""

        try:
            async for entry in guild.audit_logs(limit=limit, action=action):
                if entry.target and entry.target.id == target_id:
                    if (datetime.now(timezone.utc) - entry.created_at).total_seconds() > 10:
                        continue

                    logger.debug("Found audit log actor %s for action %s target %s", entry.user.id, action, target_id)
                    return entry.user
                
        except Exception as e:
            logger.warning("Не удалось получить аудит-лог для действия %s: %s", action, e)

        return None

    def _guild_from_id(self, guild_id: int) -> Optional[disnake.Guild]:
        if self._bot:
            return self._bot.get_guild(guild_id)
        return None
