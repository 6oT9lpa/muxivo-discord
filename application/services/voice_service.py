from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set, Tuple

import disnake

from application.dto.voice_dto import VoiceRoomDTO
from application.schemas.voice_schemas import (
    VoiceInviteSchema,
    VoiceLimitSchema,
    VoiceRenameSchema,
)
from core.interfaces.repositories import VoiceRepositoryInterface
from core.interfaces.services import LoggingServiceInterface, VoiceServiceInterface
from infrastructure.logging import get_logger

logger = get_logger(__name__)

_MSK = timezone(timedelta(hours=3))


class VoiceService(VoiceServiceInterface):
    def __init__(self, repo: VoiceRepositoryInterface, logging_service: Optional[LoggingServiceInterface] = None) -> None:
        self._repo = repo
        self._logging_service = logging_service
        self._delete_tasks: Dict[int, asyncio.Task] = {}
        self._owner_transfer_tasks: Dict[int, asyncio.Task] = {}
        self._creating: Set[Tuple[int, int]] = set()

    async def create(
        self,
        member: disnake.Member,
        trigger_channel: disnake.VoiceChannel,
    ) -> Optional[disnake.VoiceChannel]:
        key = (member.id, member.guild.id)
        logger.info("Voice room create requested: guild_id=%s user_id=%s", member.guild.id, member.id)
        if key in self._creating:
            logger.debug("Already creating room for user_id=%s", member.id)
            return None

        existing = await self._repo.get_by_owner(member.id, member.guild.id)
        if existing:
            channel = member.guild.get_channel(existing["channel_id"])
            if channel:
                try:
                    await member.move_to(channel)
                    logger.debug("Redirected user_id=%s to existing room", member.id)
                except Exception as exc:
                    logger.warning("Failed to redirect user_id=%s: %s", member.id, exc)
                return None
            await self._repo.delete(existing["channel_id"])
            logger.warning("Stale voice room removed: channel_id=%s", existing["channel_id"])

        self._creating.add(key)
        try:
            return await self._create_room(member, trigger_channel)
        finally:
            self._creating.discard(key)

    async def delete(self, channel: disnake.VoiceChannel) -> None:
        logger.info("Voice room delete requested: channel_id=%s", channel.id)
        try:
            self._cancel_owner_task(channel.id)
            await self._repo.delete(channel.id)
            await channel.delete()
            logger.info("Voice room deleted: channel_id=%s name=%s", channel.id, channel.name)
        except Exception as exc:
            logger.error("Failed to delete voice room channel_id=%s: %s", channel.id, exc)
            raise

    async def schedule_delete(self, channel: disnake.VoiceChannel, delay: float = 10.0) -> None:
        self._cancel_task(channel.id)

        async def _delayed_delete() -> None:
            try:
                await asyncio.sleep(delay)
                if not channel.members:
                    await self.delete(channel)
            finally:
                self._delete_tasks.pop(channel.id, None)

        self._delete_tasks[channel.id] = asyncio.create_task(_delayed_delete())
        logger.debug("Scheduled delete for channel_id=%s in %.0fs", channel.id, delay)

    async def cancel_delete(self, channel_id: int) -> None:
        self._cancel_task(channel_id)

    async def schedule_owner_transfer(
        self,
        channel: disnake.VoiceChannel,
        old_owner: disnake.Member,
        delay: float = 10.0,
    ) -> None:
        self._cancel_owner_task(channel.id)

        async def _delayed_transfer() -> None:
            try:
                await asyncio.sleep(delay)
                await self._transfer_owner_if_absent(channel, old_owner)
            finally:
                self._owner_transfer_tasks.pop(channel.id, None)

        self._owner_transfer_tasks[channel.id] = asyncio.create_task(_delayed_transfer())
        logger.info("Owner transfer scheduled: channel_id=%s owner_id=%s delay=%.0fs", channel.id, old_owner.id, delay)

    async def cancel_owner_transfer(self, channel_id: int) -> None:
        self._cancel_owner_task(channel_id)

    async def handle_admin_leave(
        self,
        channel: disnake.VoiceChannel,
        old_admin: disnake.Member,
    ) -> None:
        # Admin remains temporary and is independent from delayed owner transfer.
        room = await self._repo.get(channel.id)
        admin_id = int(room["admin_id"]) if room and room.get("admin_id") else None
        if not room or admin_id != old_admin.id:
            logger.debug("Skip admin leave handling channel_id=%s user_id=%s", channel.id, old_admin.id)
            return

        try:
            await self._clear_admin(channel, old_admin)
            logger.info("Temporary voice admin cleared on leave: channel_id=%s admin_id=%s", channel.id, old_admin.id)
        except Exception as exc:
            logger.error("Failed to clear voice admin on leave channel_id=%s: %s", channel.id, exc)
            raise

    async def rename(
        self,
        channel: disnake.VoiceChannel,
        new_name: str,
        user: disnake.Member,
    ) -> None:
        logger.info("Voice room rename requested: channel_id=%s user_id=%s", channel.id, user.id)
        if not await self._can_control(user, channel):
            logger.warning("User %s lacks voice control for rename in %s", user.id, channel.id)
            raise PermissionError("Not enough rights to rename the room")

        schema = VoiceRenameSchema(name=new_name)
        try:
            await channel.edit(name=schema.name)
            logger.debug("Voice room renamed: channel_id=%s new_name=%s user_id=%s", channel.id, schema.name, user.id)
        except Exception as exc:
            logger.error("Failed to rename channel_id=%s: %s", channel.id, exc)
            raise

    async def set_limit(
        self,
        channel: disnake.VoiceChannel,
        limit: int,
        user: disnake.Member,
    ) -> None:
        logger.info("Voice room limit requested: channel_id=%s user_id=%s limit=%s", channel.id, user.id, limit)
        if not await self._can_control(user, channel):
            logger.warning("User %s lacks voice control for limit in %s", user.id, channel.id)
            raise PermissionError("Not enough rights to set the room limit")

        schema = VoiceLimitSchema(limit=limit)
        try:
            await channel.edit(user_limit=schema.limit)
            logger.debug("Voice limit set: channel_id=%s limit=%s user_id=%s", channel.id, schema.limit, user.id)
        except Exception as exc:
            logger.error("Failed to set limit channel_id=%s: %s", channel.id, exc)
            raise

    async def lock(self, channel: disnake.VoiceChannel, user: disnake.Member) -> None:
        logger.info("Voice room lock requested: channel_id=%s user_id=%s", channel.id, user.id)
        await self._set_everyone_connect(channel, user, allow=False)

    async def unlock(self, channel: disnake.VoiceChannel, user: disnake.Member) -> None:
        logger.info("Voice room unlock requested: channel_id=%s user_id=%s", channel.id, user.id)
        await self._set_everyone_connect(channel, user, allow=True)

    async def transfer(
        self,
        channel: disnake.VoiceChannel,
        new_owner: disnake.Member,
        user: disnake.Member,
    ) -> None:
        await self.assign_admin(channel, new_owner, user)

    async def claim_admin(self, channel: disnake.VoiceChannel, user: disnake.Member) -> None:
        logger.info("Voice admin claim requested: channel_id=%s user_id=%s", channel.id, user.id)
        room = await self._require_room(channel)
        if int(room["owner_id"]) == user.id:
            logger.warning("Owner %s attempted to claim admin in channel_id=%s", user.id, channel.id)
            raise PermissionError("Owner cannot become admin")
        admin_id = int(room["admin_id"]) if room.get("admin_id") else None
        if admin_id and admin_id != user.id:
            logger.warning("User %s attempted to claim occupied admin channel_id=%s", user.id, channel.id)
            raise PermissionError("Admin rights are already taken")

        if admin_id == user.id:
            return

        if not await self._repo.claim_admin(channel.id, user.id):
            raise PermissionError("Admin rights are already taken")
        try:
            await channel.set_permissions(
                user,
                connect=True,
                manage_channels=True,
                manage_permissions=True,
                move_members=True,
            )
        except Exception:
            await self._repo.clear_admin_if(channel.id, user.id)
            raise
        logger.info("Temporary voice admin claimed: channel_id=%s admin_id=%s", channel.id, user.id)

    async def shutdown(self) -> None:
        pending = set(self._delete_tasks.values()) | set(self._owner_transfer_tasks.values())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._delete_tasks.clear()
        self._owner_transfer_tasks.clear()

    async def release_admin(self, channel: disnake.VoiceChannel, user: disnake.Member) -> None:
        logger.info("Voice admin release requested: channel_id=%s user_id=%s", channel.id, user.id)
        room = await self._require_room(channel)
        admin_id = int(room["admin_id"]) if room.get("admin_id") else None
        if admin_id != user.id:
            logger.warning("User %s attempted to release admin in channel_id=%s", user.id, channel.id)
            raise PermissionError("Only current admin can release admin rights")

        await self._clear_admin(channel, user)
        logger.info("Temporary voice admin released: channel_id=%s admin_id=%s", channel.id, user.id)

    async def assign_admin(
        self,
        channel: disnake.VoiceChannel,
        new_admin: Optional[disnake.Member],
        user: disnake.Member,
    ) -> None:
        logger.info(
            "Voice admin assignment requested: channel_id=%s user_id=%s target_id=%s",
            channel.id,
            user.id,
            getattr(new_admin, "id", None),
        )
        room = await self._require_room(channel)
        if int(room["owner_id"]) != user.id:
            logger.warning("User %s attempted owner-only admin assignment channel_id=%s", user.id, channel.id)
            raise PermissionError("Only owner can assign admin rights")
        if new_admin and new_admin.id == int(room["owner_id"]):
            logger.warning("Owner %s cannot be assigned as admin channel_id=%s", new_admin.id, channel.id)
            raise PermissionError("Owner cannot become admin")
        if new_admin and new_admin.bot:
            logger.warning("Bot %s cannot be assigned as admin channel_id=%s", new_admin.id, channel.id)
            raise PermissionError("Bot cannot become admin")

        current_admin = self._member_from_room(channel, room.get("admin_id"))
        if current_admin:
            await self._clear_admin(channel, current_admin)
        elif room.get("admin_id"):
            await self._repo.update_admin(channel.id, None)

        if new_admin:
            await self._grant_admin(channel, new_admin)
            logger.info("Temporary voice admin assigned: channel_id=%s owner_id=%s admin_id=%s", channel.id, user.id, new_admin.id)
        else:
            logger.info("Temporary voice admin cleared by owner: channel_id=%s owner_id=%s", channel.id, user.id)

    async def track_member_join(self, channel: disnake.VoiceChannel, member: disnake.Member) -> bool:
        room = await self._repo.get(channel.id)
        if not room:
            logger.debug("Skip voice member join tracking because room is missing channel_id=%s user_id=%s", channel.id, member.id)
            return False
        if self._is_banned_from_room(channel, member):
            await member.move_to(None)
            logger.info("Banned voice member removed on join: channel_id=%s user_id=%s", channel.id, member.id)
            return False
        if int(room["owner_id"]) == member.id:
            await self.cancel_owner_transfer(channel.id)
            logger.info("Owner transfer cancelled because owner rejoined: channel_id=%s owner_id=%s", channel.id, member.id)
        await self._repo.add_member(channel.id, member.guild.id, member.id)
        logger.debug("Voice member join tracked: guild_id=%s channel_id=%s user_id=%s", member.guild.id, channel.id, member.id)
        return True

    async def track_member_leave(self, channel: disnake.VoiceChannel, member: disnake.Member) -> None:
        room = await self._repo.get(channel.id)
        if not room:
            logger.debug("Skip voice member leave tracking because room is missing channel_id=%s user_id=%s", channel.id, member.id)
            return
        await self._repo.remove_member(channel.id, member.id)
        logger.debug("Voice member leave tracked: guild_id=%s channel_id=%s user_id=%s", member.guild.id, channel.id, member.id)

    async def invite(
        self,
        channel: disnake.VoiceChannel,
        target: disnake.Member,
        user: disnake.Member,
    ) -> None:
        logger.info("Voice invite requested: channel_id=%s user_id=%s target_id=%s", channel.id, user.id, target.id)
        if not await self._can_control(user, channel):
            logger.warning("User %s lacks voice control for invite in %s", user.id, channel.id)
            raise PermissionError("Not enough rights to invite users")

        schema = VoiceInviteSchema(user_id=target.id)
        try:
            await channel.set_permissions(target, connect=True)
            await self._try_dm_invite(target, user, channel)
            await self._try_channel_invite_notice(target, user, channel)
            logger.debug("Invited user_id=%s to channel_id=%s by user_id=%s", schema.user_id, channel.id, user.id)
        except Exception as exc:
            logger.error("Failed to invite target_id=%s channel_id=%s: %s", target.id, channel.id, exc)
            raise

    async def kick(
        self,
        channel: disnake.VoiceChannel,
        target: disnake.Member,
        user: disnake.Member,
    ) -> None:
        await self._remove_from_room(channel, target, user, ban=False)

    async def ban(
        self,
        channel: disnake.VoiceChannel,
        target: disnake.Member,
        user: disnake.Member,
    ) -> None:
        await self._remove_from_room(channel, target, user, ban=True)

    async def set_trigger(self, guild_id: int, channel_id: int) -> None:
        await self._repo.set_config(f"trigger_{guild_id}", str(channel_id))
        logger.info("Trigger set for guild %s: channel %s", guild_id, channel_id)

    async def get_trigger(self, guild_id: int) -> Optional[int]:
        value = await self._repo.get_config(f"trigger_{guild_id}")
        logger.debug("Trigger fetched for guild_id=%s exists=%s", guild_id, bool(value))
        return int(value) if value else None

    async def remove_trigger(self, guild_id: int) -> None:
        await self._repo.set_config(f"trigger_{guild_id}", "")
        logger.info("Trigger removed for guild %s", guild_id)

    async def _create_room(
        self,
        member: disnake.Member,
        trigger_channel: disnake.VoiceChannel,
    ) -> Optional[disnake.VoiceChannel]:
        guild = member.guild
        room_name = f"🔊 {member.display_name}"

        channel: Optional[disnake.VoiceChannel] = None

        try:
            channel = await guild.create_voice_channel(
                name=room_name,
                category=trigger_channel.category,
            )
            await channel.set_permissions(
                member,
                connect=True,
                manage_channels=True,
                manage_permissions=True,
                move_members=True,
            )
            await member.move_to(channel)
            await self._repo.create(
                VoiceRoomDTO(
                    channel_id=channel.id,
                    guild_id=guild.id,
                    owner_id=member.id,
                    admin_id=None,
                    name=room_name,
                    created_at=datetime.now(_MSK),
                )
            )
            await self._repo.add_member(channel.id, guild.id, member.id)
            logger.info("Voice room created: channel_id=%s name=%s owner=%s", channel.id, room_name, member.id)
            return channel
        except Exception as exc:
            if channel:
                try:
                    await channel.delete(reason="Muxivo Discord voice room metadata creation failed")
                    logger.warning("Rolled back orphan voice room after create failure: channel_id=%s", channel.id)
                except Exception as rollback_exc:
                    logger.error(
                        "Failed to roll back orphan voice room channel_id=%s: %s",
                        channel.id,
                        rollback_exc,
                    )
            logger.error("Failed to create voice room for user_id=%s: %s", member.id, exc)
            raise

    async def _grant_admin(self, channel: disnake.VoiceChannel, admin: disnake.Member) -> None:
        await channel.set_permissions(
            admin,
            connect=True,
            manage_channels=True,
            manage_permissions=True,
            move_members=True,
        )
        await self._repo.update_admin(channel.id, admin.id)
        logger.debug("Admin permissions granted: channel_id=%s admin_id=%s", channel.id, admin.id)

    async def _clear_admin(self, channel: disnake.VoiceChannel, admin: disnake.Member) -> None:
        room = await self._require_room(channel)
        if int(room["owner_id"]) != admin.id:
            await channel.set_permissions(admin, overwrite=None)
        await self._repo.update_admin(channel.id, None)
        logger.debug("Admin permissions cleared: channel_id=%s admin_id=%s", channel.id, admin.id)

    async def _set_everyone_connect(
        self,
        channel: disnake.VoiceChannel,
        user: disnake.Member,
        *,
        allow: bool,
    ) -> None:
        if not await self._can_control(user, channel):
            logger.warning("User %s lacks voice control for lock/unlock in %s", user.id, channel.id)
            raise PermissionError("Not enough rights to change room access")

        try:
            await channel.set_permissions(user.guild.default_role, connect=allow)
            logger.debug("Channel connect=%s channel_id=%s user_id=%s", allow, channel.id, user.id)
        except Exception as exc:
            logger.error("Failed to set connect permission channel_id=%s: %s", channel.id, exc)
            raise

    async def _remove_from_room(
        self,
        channel: disnake.VoiceChannel,
        target: disnake.Member,
        user: disnake.Member,
        *,
        ban: bool,
    ) -> None:
        if not await self._can_control(user, channel):
            logger.warning("User %s lacks voice control for kick/ban in %s", user.id, channel.id)
            raise PermissionError("Not enough rights to remove users")
        room = await self._require_room(channel)
        owner_id = int(room["owner_id"])
        if target.id == user.id:
            logger.warning("User %s attempted to remove themselves from channel_id=%s", user.id, channel.id)
            raise PermissionError("You cannot kick or ban yourself")
        if target.id == owner_id:
            logger.warning("User %s attempted to remove owner %s from channel_id=%s", user.id, target.id, channel.id)
            raise PermissionError("Owner cannot be kicked or banned from the room")
        if ban and room.get("admin_id") and int(room["admin_id"]) == target.id:
            await self._clear_admin(channel, target)
            logger.info("Temporary voice admin cleared before ban: channel_id=%s admin_id=%s", channel.id, target.id)

        try:
            await channel.set_permissions(target, connect=False)
            if target.voice and target.voice.channel == channel:
                await target.move_to(None)
            action = "banned" if ban else "kicked"
            logger.debug("User %s from channel_id=%s target_id=%s by user_id=%s", action, channel.id, target.id, user.id)
        except Exception as exc:
            logger.error("Failed to remove target_id=%s from channel_id=%s: %s", target.id, channel.id, exc)
            raise

    async def _try_dm_invite(
        self,
        target: disnake.Member,
        inviter: disnake.Member,
        channel: disnake.VoiceChannel,
    ) -> None:
        try:
            await target.send(embed=self._build_voice_invite_embed(target, inviter, channel, direct_message=True))
        except disnake.Forbidden:
            logger.debug("DM closed for target_id=%s", target.id)
        except Exception as exc:
            logger.debug("Failed to DM invite target_id=%s: %s", target.id, exc)

    async def _try_channel_invite_notice(
        self,
        target: disnake.Member,
        inviter: disnake.Member,
        channel: disnake.VoiceChannel,
    ) -> None:
        sender = getattr(channel, "send", None)
        if not sender:
            logger.debug("Voice invite channel notice skipped because channel has no send method channel_id=%s", channel.id)
            return
        try:
            await sender(
                target.mention,
                embed=self._build_voice_invite_embed(target, inviter, channel, direct_message=False),
                allowed_mentions=disnake.AllowedMentions(users=True),
            )
        except Exception as exc:
            logger.warning(
                "Voice invite channel notice failed target_id=%s channel_id=%s: %s",
                target.id,
                channel.id,
                exc,
            )

    def _build_voice_invite_embed(
        self,
        target: disnake.Member,
        inviter: disnake.Member,
        channel: disnake.VoiceChannel,
        *,
        direct_message: bool,
    ) -> disnake.Embed:
        channel_url = self._voice_channel_url(channel)
        title = "Приглашение в голосовую комнату" if direct_message else "Голосовое приглашение"
        description = (
            f"{inviter.mention} приглашает вас присоединиться к **{channel.name}**."
            if direct_message
            else f"{inviter.mention} приглашает {target.mention} присоединиться к **{channel.name}**."
        )
        if channel_url:
            description = f"{description}\n\n[Перейти в комнату]({channel_url})"

        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.blurple(),
            timestamp=datetime.now(_MSK),
        )
        embed.add_field(name="Комната", value=channel.mention, inline=True)
        embed.add_field(name="Пригласил", value=inviter.mention, inline=True)
        embed.add_field(name="Доступ", value="Разрешение на вход уже выдано.", inline=False)
        embed.set_footer(text="Muxivo Discord Voice Rooms")

        inviter_avatar_url = self._avatar_url(inviter)
        if inviter_avatar_url:
            embed.set_author(name=inviter.display_name, icon_url=inviter_avatar_url)
            embed.set_thumbnail(url=inviter_avatar_url)
        else:
            embed.set_author(name=inviter.display_name)
        return embed

    def _voice_channel_url(self, channel: disnake.VoiceChannel) -> Optional[str]:
        jump_url = getattr(channel, "jump_url", None)
        if jump_url:
            return str(jump_url)
        guild = getattr(channel, "guild", None)
        guild_id = getattr(guild, "id", None)
        if guild_id:
            return f"https://discord.com/channels/{guild_id}/{channel.id}"
        return None

    def _avatar_url(self, member: disnake.Member) -> Optional[str]:
        avatar = getattr(member, "display_avatar", None) or getattr(member, "avatar", None)
        url = getattr(avatar, "url", None)
        return str(url) if url else None

    async def _require_room(self, channel: disnake.VoiceChannel) -> dict:
        room = await self._repo.get(channel.id)
        if not room:
            logger.warning("Voice room metadata missing: channel_id=%s", channel.id)
            raise PermissionError("Voice room metadata was not found")
        return room

    def _member_from_room(self, channel: disnake.VoiceChannel, member_id: Optional[int]) -> Optional[disnake.Member]:
        if not member_id:
            return None
        return channel.guild.get_member(int(member_id))

    async def _can_control(self, user: disnake.Member, channel: disnake.VoiceChannel) -> bool:
        room = await self._repo.get(channel.id)
        if not room:
            logger.debug("Control denied because room metadata is missing channel_id=%s user_id=%s", channel.id, user.id)
            return False
        admin_id = int(room["admin_id"]) if room.get("admin_id") else None
        if int(room["owner_id"]) == user.id or admin_id == user.id:
            return True
        return self._has_manage_permissions(user, channel)

    def _cancel_task(self, channel_id: int) -> None:
        task = self._delete_tasks.pop(channel_id, None)
        if task:
            task.cancel()
            logger.debug("Delete task cancelled for channel_id=%s", channel_id)

    def _cancel_owner_task(self, channel_id: int) -> None:
        task = self._owner_transfer_tasks.pop(channel_id, None)
        if task:
            task.cancel()
            logger.debug("Owner transfer task cancelled for channel_id=%s", channel_id)

    async def _transfer_owner_if_absent(
        self,
        channel: disnake.VoiceChannel,
        old_owner: disnake.Member,
    ) -> None:
        room = await self._repo.get(channel.id)
        if not room:
            logger.debug("Owner transfer skipped because room is missing channel_id=%s", channel.id)
            return
        if int(room["owner_id"]) != old_owner.id:
            logger.debug("Owner transfer skipped because owner already changed channel_id=%s", channel.id)
            return
        if self._is_connected_to_channel(old_owner, channel):
            logger.debug("Owner transfer skipped because owner returned channel_id=%s owner_id=%s", channel.id, old_owner.id)
            return

        candidates = [
            member
            for member in channel.members
            if not member.bot and member.id != old_owner.id and self._is_connected_to_channel(member, channel)
        ]
        if not candidates:
            logger.info("Owner transfer skipped because no candidates remain channel_id=%s owner_id=%s", channel.id, old_owner.id)
            return

        new_owner = random.choice(candidates)
        await self._grant_owner(channel, old_owner, new_owner, room)
        logger.info(
            "Voice owner transferred: channel_id=%s old_owner_id=%s new_owner_id=%s",
            channel.id,
            old_owner.id,
            new_owner.id,
        )

    async def _grant_owner(
        self,
        channel: disnake.VoiceChannel,
        old_owner: disnake.Member,
        new_owner: disnake.Member,
        room: dict,
    ) -> None:
        if room.get("admin_id") and int(room["admin_id"]) == new_owner.id:
            await self._repo.update_admin(channel.id, None)
            logger.info("Temporary admin cleared because admin became owner: channel_id=%s user_id=%s", channel.id, new_owner.id)
        await channel.set_permissions(old_owner, overwrite=None)
        await channel.set_permissions(
            new_owner,
            connect=True,
            manage_channels=True,
            manage_permissions=True,
            move_members=True,
        )
        await self._repo.update_owner(channel.id, new_owner.id)
        if self._logging_service:
            await self._logging_service.log_voice_owner_transfer(channel, old_owner, new_owner)

    @staticmethod
    def _has_manage_permissions(user: disnake.Member, channel: disnake.VoiceChannel) -> bool:
        return channel.permissions_for(user).manage_permissions

    @staticmethod
    def _is_connected_to_channel(member: disnake.Member, channel: disnake.VoiceChannel) -> bool:
        voice_state = getattr(member, "voice", None)
        return voice_state == channel or getattr(voice_state, "channel", None) == channel

    @staticmethod
    def _is_banned_from_room(channel: disnake.VoiceChannel, member: disnake.Member) -> bool:
        try:
            overwrite = channel.overwrites_for(member)
        except Exception as exc:
            logger.debug("Failed to inspect voice overwrite channel_id=%s user_id=%s: %s", channel.id, member.id, exc)
            return False
        return overwrite.connect is False
