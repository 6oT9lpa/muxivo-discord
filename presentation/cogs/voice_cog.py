from __future__ import annotations

import disnake
from disnake.ext import commands

from core.interfaces.services.voice_service_interface import VoiceServiceInterface
from infrastructure.logging import get_logger
from presentation.views.voice_views import VoiceControlView, build_voice_control_embed

logger = get_logger(__name__)


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot, service: VoiceServiceInterface) -> None:
        self._bot = bot
        self._service = service
        self._trigger_cache: dict[int, int] = {}
        self._startup_task = self._bot.loop.create_task(self._on_start())

    def cog_unload(self) -> None:
        if not self._startup_task.done():
            self._startup_task.cancel()

    async def _on_start(self) -> None:
        await self._bot.wait_until_ready()
        self._bot.add_view(VoiceControlView(self._service, timeout=None))
        for guild in self._bot.guilds:
            trigger = await self._service.get_trigger(guild.id)
            if trigger is not None:
                self._trigger_cache[guild.id] = trigger
        logger.info("VoiceCog loaded, trigger_count=%s", len(self._trigger_cache))

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: disnake.Member,
        before: disnake.VoiceState,
        after: disnake.VoiceState,
    ) -> None:
        if member.bot:
            logger.debug("Ignoring bot voice state update user_id=%s", member.id)
            return

        if before.channel == after.channel:
            logger.debug("Ignoring voice state-only update for user_id=%s channel_id=%s", member.id, getattr(after.channel, "id", None))
            return

        guild = member.guild
        trigger_id = await self._service.get_trigger(guild.id) or self._trigger_cache.get(guild.id)

        if after.channel and trigger_id and after.channel.id == trigger_id:
            logger.info("Voice trigger entered: guild_id=%s user_id=%s trigger_id=%s", guild.id, member.id, trigger_id)
            existing = await self._service._repo.get_by_owner(member.id, guild.id)
            if existing:
                channel = guild.get_channel(existing["channel_id"])
                if channel and channel.id != after.channel.id:
                    try:
                        await member.move_to(channel)
                        logger.info("Redirected member to existing voice room: user_id=%s channel_id=%s", member.id, channel.id)
                    except Exception as exc:
                        logger.warning("Failed to redirect member %s: %s", member.id, exc)
                    return
            else:
                try:
                    channel = await self._service.create(member, after.channel)
                except Exception:
                    logger.exception("Dynamic voice room creation failed guild_id=%s user_id=%s", guild.id, member.id)
                    return
                if channel:
                    try:
                        await channel.send(embed=build_voice_control_embed(member), view=VoiceControlView(self._service))
                        logger.info("Voice control panel sent: channel_id=%s owner_id=%s", channel.id, member.id)
                    except Exception:
                        logger.exception("Failed to send voice control panel: channel_id=%s owner_id=%s", channel.id, member.id)
            return

        if before.channel:
            room = await self._service._repo.get(before.channel.id)
            if room:
                await self._service.track_member_leave(before.channel, member)
                admin_id = int(room["admin_id"]) if room.get("admin_id") else None
                if admin_id == member.id:
                    await self._service.handle_admin_leave(before.channel, member)
                if len(before.channel.members) == 0:
                    await self._service.schedule_delete(before.channel)
                    logger.info("Voice room became empty, deletion scheduled: channel_id=%s", before.channel.id)
                elif int(room["owner_id"]) == member.id:
                    await self._service.schedule_owner_transfer(before.channel, member)

        joined_channel = after.channel
        if joined_channel:
            room = await self._service._repo.get(joined_channel.id)
            if room:
                tracked = await self._service.track_member_join(joined_channel, member)
                if not tracked:
                    return
                await self._service.cancel_delete(joined_channel.id)
                logger.debug("Voice room delete cancelled after join: channel_id=%s user_id=%s", joined_channel.id, member.id)

    @commands.slash_command(description="Голосовые комнаты")
    async def voice(self, inter: disnake.ApplicationCommandInteraction) -> None:
        pass

    @commands.slash_command(name="send", description="Опустить панель управления текущей voice-комнатой вниз")
    async def send_panel(self, inter: disnake.ApplicationCommandInteraction) -> None:
        channel = inter.author.voice.channel if inter.author.voice else None
        if not channel:
            await inter.response.send_message("Вы не в голосовой комнате.", ephemeral=True)
            logger.debug("/send rejected because user has no voice channel user_id=%s", inter.author.id)
            return

        room = await self._service._repo.get(channel.id)
        if not room:
            await inter.response.send_message("Это не динамическая комната Muxivo Discord.", ephemeral=True)
            logger.debug("/send rejected because room metadata is missing channel_id=%s", channel.id)
            return

        owner = inter.guild.get_member(int(room["owner_id"]))
        admin = inter.guild.get_member(int(room["admin_id"])) if room.get("admin_id") else None
        if not owner:
            await inter.response.send_message("Owner комнаты не найден на сервере.", ephemeral=True)
            logger.warning("/send failed because owner is missing channel_id=%s owner_id=%s", channel.id, room["owner_id"])
            return

        await channel.send(embed=build_voice_control_embed(owner, admin), view=VoiceControlView(self._service))
        await inter.response.send_message("Панель отправлена вниз чата.", ephemeral=True)
        logger.info("Voice control panel resent by /send: channel_id=%s user_id=%s", channel.id, inter.author.id)

    @voice.sub_command(description="Установить trigger-канал")
    async def set_trigger(
        self,
        inter: disnake.ApplicationCommandInteraction,
        канал: disnake.VoiceChannel,
    ) -> None:
        if not inter.author.guild_permissions.administrator:
            await inter.response.send_message("Только администратор может менять trigger.", ephemeral=True)
            logger.warning("Voice trigger set denied user_id=%s", inter.author.id)
            return

        await self._service.set_trigger(inter.guild.id, канал.id)
        self._trigger_cache[inter.guild.id] = канал.id
        await inter.response.send_message(f"{канал.mention} установлен как trigger.", ephemeral=True)
        logger.info("Voice trigger set: guild_id=%s channel_id=%s user_id=%s", inter.guild.id, канал.id, inter.author.id)

    @voice.sub_command(description="Удалить trigger-канал")
    async def remove_trigger(self, inter: disnake.ApplicationCommandInteraction) -> None:
        if not inter.author.guild_permissions.administrator:
            await inter.response.send_message("Только администратор может менять trigger.", ephemeral=True)
            logger.warning("Voice trigger remove denied user_id=%s", inter.author.id)
            return

        await self._service.remove_trigger(inter.guild.id)
        self._trigger_cache.pop(inter.guild.id, None)
        await inter.response.send_message("Trigger удален.", ephemeral=True)
        logger.info("Voice trigger removed: guild_id=%s user_id=%s", inter.guild.id, inter.author.id)
