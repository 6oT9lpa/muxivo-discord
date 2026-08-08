from __future__ import annotations

from typing import Callable, Optional

import disnake

from core.interfaces.services.voice_service_interface import VoiceServiceInterface
from infrastructure.logging import get_logger
from presentation.views.voice_control.member_select_view import MemberSelectView
from presentation.views.voice_control.panel_refresh import refresh_voice_control_panel
from presentation.views.voice_control.voice_invite_modal import VoiceInviteModal
from presentation.views.voice_control.voice_limit_modal import VoiceLimitModal
from presentation.views.voice_control.voice_rename_modal import VoiceRenameModal

logger = get_logger(__name__)


class VoiceActionSelect(disnake.ui.StringSelect):
    def __init__(self, service: VoiceServiceInterface) -> None:
        self.service = service
        super().__init__(
            custom_id="voice:actions",
            placeholder="Action",
            min_values=1,
            max_values=1,
            options=[
                disnake.SelectOption(label="Rename", value="rename", description="Change room name"),
                disnake.SelectOption(label="Limit", value="limit", description="Change user limit"),
                disnake.SelectOption(label="Lock", value="lock", description="Close the room"),
                disnake.SelectOption(label="Unlock", value="unlock", description="Open the room"),
                disnake.SelectOption(label="Invite", value="invite", description="Allow a user to connect"),
                disnake.SelectOption(label="Kick", value="kick", description="Disconnect a user"),
                disnake.SelectOption(label="Ban", value="ban", description="Deny a user access"),
                disnake.SelectOption(label="Take Admin", value="take_admin", description="Claim free admin rights"),
                disnake.SelectOption(label="Assign Admin", value="assign_admin", description="Owner assigns admin"),
                disnake.SelectOption(label="Clear Admin", value="clear_admin", description="Remove admin rights"),
            ],
        )

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        context = await self._resolve_context(inter)
        if context is None:
            return

        channel, room = context
        action = self.values[0]
        logger.info("Voice action selected: action=%s channel_id=%s user_id=%s", action, channel.id, inter.author.id)
        handlers: dict[str, Callable[[disnake.MessageInteraction], object]] = {
            "rename": lambda interaction: self._owner_or_admin_modal(interaction, room, VoiceRenameModal(self.service)),
            "limit": lambda interaction: self._owner_or_admin_modal(interaction, room, VoiceLimitModal(self.service)),
            "lock": lambda interaction: self._lock(interaction, channel, room),
            "unlock": lambda interaction: self._unlock(interaction, channel, room),
            "invite": lambda interaction: self._owner_or_admin_modal(interaction, room, VoiceInviteModal(self.service)),
            "kick": lambda interaction: self._member_action(interaction, channel, room, "kick"),
            "ban": lambda interaction: self._member_action(interaction, channel, room, "ban"),
            "take_admin": lambda interaction: self._take_admin(interaction, channel, room),
            "assign_admin": lambda interaction: self._member_action(interaction, channel, room, "assign_admin"),
            "clear_admin": lambda interaction: self._clear_admin(interaction, channel, room),
        }
        handler = handlers.get(action)
        if handler is None:
            await inter.response.send_message("Unknown voice action.", ephemeral=True)
            return
        await handler(inter)

    async def _owner_or_admin_modal(self, inter: disnake.MessageInteraction, room: dict, modal: object) -> None:
        if not self._is_owner_or_admin(inter.author, room):
            await inter.response.send_message("This action is available only to the owner or admin.", ephemeral=True)
            return
        await inter.response.send_modal(modal)

    async def _lock(self, inter: disnake.MessageInteraction, channel: disnake.VoiceChannel, room: dict) -> None:
        if not self._is_owner_or_admin(inter.author, room):
            await inter.response.send_message("This action is available only to the owner or admin.", ephemeral=True)
            return
        try:
            await self.service.lock(channel, inter.author)
            await inter.response.send_message("Room locked.", ephemeral=True)
        except PermissionError as exc:
            await inter.response.send_message(str(exc), ephemeral=True)

    async def _unlock(self, inter: disnake.MessageInteraction, channel: disnake.VoiceChannel, room: dict) -> None:
        if not self._is_owner_or_admin(inter.author, room):
            await inter.response.send_message("This action is available only to the owner or admin.", ephemeral=True)
            return
        try:
            await self.service.unlock(channel, inter.author)
            await inter.response.send_message("Room unlocked.", ephemeral=True)
        except PermissionError as exc:
            await inter.response.send_message(str(exc), ephemeral=True)

    async def _member_action(
        self,
        inter: disnake.MessageInteraction,
        channel: disnake.VoiceChannel,
        room: dict,
        action: str,
    ) -> None:
        if action == "assign_admin" and not self._is_owner(inter.author, room):
            await inter.response.send_message("Only the owner can assign admin.", ephemeral=True)
            return
        if action in {"kick", "ban"} and not self._is_owner_or_admin(inter.author, room):
            await inter.response.send_message("This action is available only to the owner or admin.", ephemeral=True)
            return

        owner_id = int(room["owner_id"])
        members = [
            member
            for member in channel.members
            if not member.bot
            and member.id != inter.author.id
            and (action not in {"kick", "ban"} or member.id != owner_id)
        ]
        if not members:
            await inter.response.send_message("No available voice members.", ephemeral=True)
            return

        await inter.response.send_message(
            "Choose a voice member:",
            view=MemberSelectView(self.service, channel, action, members),
            ephemeral=True,
        )

    async def _take_admin(self, inter: disnake.MessageInteraction, channel: disnake.VoiceChannel, room: dict) -> None:
        if room.get("admin_id"):
            await inter.response.send_message("Admin rights are already taken.", ephemeral=True)
            return
        try:
            await self.service.claim_admin(channel, inter.author)
            await self._refresh_panel(channel, inter.author)
            await inter.response.send_message("Admin rights claimed.", ephemeral=True)
        except PermissionError as exc:
            await inter.response.send_message(str(exc), ephemeral=True)

    async def _clear_admin(self, inter: disnake.MessageInteraction, channel: disnake.VoiceChannel, room: dict) -> None:
        if not self._is_owner_or_admin(inter.author, room):
            await inter.response.send_message("Only the owner or admin can clear admin rights.", ephemeral=True)
            return
        if not room.get("admin_id"):
            await inter.response.send_message("Admin rights are already free.", ephemeral=True)
            return

        if self._is_owner(inter.author, room):
            await self.service.assign_admin(channel, None, inter.author)
        else:
            await self.service.release_admin(channel, inter.author)
        await self._refresh_panel(channel, None)
        await inter.response.send_message("Admin rights cleared.", ephemeral=True)

    async def _resolve_context(self, inter: disnake.MessageInteraction) -> tuple[disnake.VoiceChannel, dict] | None:
        channel = inter.author.voice.channel if inter.author.voice else None
        if not isinstance(channel, disnake.VoiceChannel):
            await inter.response.send_message("Join a voice room first.", ephemeral=True)
            logger.debug("Voice action rejected because user is not in voice: user_id=%s", inter.author.id)
            return None

        room = await self.service._repo.get(channel.id)
        if not room:
            await inter.response.send_message("This is not an Muxivo Discord dynamic voice room.", ephemeral=True)
            logger.debug("Voice action rejected because room metadata is missing channel_id=%s", channel.id)
            return None

        return channel, room

    async def _refresh_panel(self, channel: disnake.VoiceChannel, admin: Optional[disnake.Member]) -> None:
        room = await self.service._repo.get(channel.id)
        if not room:
            return
        owner = channel.guild.get_member(int(room["owner_id"]))
        if owner:
            await refresh_voice_control_panel(self.service, channel, owner, admin)

    def _is_owner(self, member: disnake.Member, room: dict) -> bool:
        return int(room["owner_id"]) == member.id

    def _is_owner_or_admin(self, member: disnake.Member, room: dict) -> bool:
        admin_id = int(room["admin_id"]) if room.get("admin_id") else None
        return self._is_owner(member, room) or admin_id == member.id
