from typing import Optional

import disnake
from disnake.ext import commands

from core.domain.channel_purpose import ChannelPurpose
from application.services import WelcomeService, ChannelService, MemberJoinHistoryService
from infrastructure.logging import get_logger
from presentation.cogs.member_events import JoinLogEmbedBuilder
from presentation.cogs.member_events import LeaveLogEmbedBuilder
from presentation.views.roles_panel_management import COLOR_GREEN, COLOR_BLUE

logger = get_logger(__name__)


class MemberEventsCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        channel_service: ChannelService,
        welcome_service: WelcomeService,
        join_history_service: MemberJoinHistoryService,
    ):
        self._bot = bot
        self._channel_service = channel_service
        self._welcome_service = welcome_service
        self._join_history_service = join_history_service
        logger.info("MemberEventsCog initialized")

    async def _get_log_channel(
        self,
        guild: disnake.Guild,
    ) -> Optional[disnake.TextChannel]:
        channel_id = await self._channel_service.get_purpose_channel(
            guild.id, ChannelPurpose.MEMBER_LOG
        )
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, disnake.TextChannel):
            logger.warning(
                f"MEMBER_LOG channel {channel_id} not found or not a TextChannel "
                f"in guild {guild.id}"
            )
            return None
        return channel

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member) -> None:
        logger.info(
            f"Member joined: {member} (id={member.id}) "
            f"in guild '{member.guild.name}' (id={member.guild.id})"
        )

        try:
            await self._join_history_service.record_join(member.guild.id, member.id, member.joined_at)
            await self._send_welcome_dm(member)
            await self._log_member_join(member)
        except Exception as e:
            logger.error(f"Error handling member join for {member.id}: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: disnake.Member) -> None:
        logger.info(
            f"Member left: {member} (id={member.id}) "
            f"in guild '{member.guild.name}' (id={member.guild.id})"
        )
        
        try:
            await self._join_history_service.record_leave(member.guild.id, member.id)
            await self._log_member_leave(member)
        except Exception as e:
            logger.error(f"Error handling member leave for {member.id}: {e}", exc_info=True)

    async def _send_welcome_dm(self, member: disnake.Member) -> None:
        try:
            logger.debug(f"Attempting to send welcome DM to {member.id}")
            config = await self._welcome_service.get_config(member.guild.id)
            embed = self._welcome_service.build_embed(member, config)
            view = await self._welcome_service.get_welcome_buttons(member.guild)
            await member.send(embed=embed, view=view)
            logger.info(f"Welcome DM sent to {member.id} in guild {member.guild.id}")
        except disnake.Forbidden:
            logger.debug(
                f"Cannot send DM to {member.id} - DMs disabled"
            )
        except Exception as e:
            logger.error(f"Failed to send welcome DM to {member.id}: {e}", exc_info=True)

    async def _log_member_join(self, member: disnake.Member) -> None:
        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            logger.debug(
                f"MEMBER_LOG channel not configured for guild {member.guild.id}"
            )
            return

        try:
            embed = JoinLogEmbedBuilder.build(member)
            await log_channel.send(embed=embed)
            logger.debug(
                f"Join log sent for {member.id} to channel {log_channel.id}"
            )
        except Exception as e:
            logger.error(f"Failed to send join log for {member.id}: {e}", exc_info=True)

    async def _log_member_leave(self, member: disnake.Member) -> None:
        log_channel = await self._get_log_channel(member.guild)
        if not log_channel:
            logger.debug(
                f"MEMBER_LOG channel not configured for guild {member.guild.id}"
            )
            return

        try:
            embed = LeaveLogEmbedBuilder.build(member)
            await log_channel.send(embed=embed)
            logger.debug(
                f"Leave log sent for {member.id} to channel {log_channel.id}"
            )
        except Exception as e:
            logger.error(f"Failed to send leave log for {member.id}: {e}", exc_info=True)

    @commands.slash_command(
        name="set_channel",
        description="Назначить канал для определённой цели",
    )
    async def set_channel(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        purpose: str = commands.Param(
            description="Назначение канала",
            choices={p.value: p.value for p in ChannelPurpose},
        ),
        channel: disnake.TextChannel = commands.Param(
            description="Канал для назначения"
        ),
    ) -> None:
        if not ctx.author.guild_permissions.administrator:
            logger.warning(f"Non-admin {ctx.author.id} attempted to use set_channel in guild {ctx.guild.id}")
            await ctx.response.send_message(
                "Только администраторы могут использовать эту команду",
                ephemeral=True,
            )
            return

        try:
            purpose_enum = ChannelPurpose(purpose)
        except ValueError:
            logger.warning(f"Invalid purpose value: {purpose}")
            await ctx.response.send_message(
                f"Неизвестное назначение: {purpose}", ephemeral=True
            )
            return

        try:
            await self._channel_service.set_purpose(
                ctx.guild.id, purpose_enum, channel.id
            )

            purpose_labels = {
                ChannelPurpose.WELCOME: "Приветствие",
                ChannelPurpose.MEMBER_LOG: "Лог входа/выхода",
                ChannelPurpose.MOD_LOG: "Лог модерации",
                ChannelPurpose.MESSAGE_LOG: "Лог сообщений",
                ChannelPurpose.CHANNEL_LOG: "Лог каналов",
                ChannelPurpose.STREAM_ANNOUNCE: "Анонсы стримов",
                ChannelPurpose.DEV_BLOG: "Dev Blog",
                ChannelPurpose.AI_MODERATION_LOG: "AI moderation log",
            }
            label = purpose_labels.get(purpose_enum, purpose)

            embed = disnake.Embed(
                title="Канал назначен",
                description=(
                    f"**{label}** — {channel.mention}\n\n"
                    f"ID канала: `{channel.id}`"
                ),
                color=COLOR_GREEN,
            )
            logger.info(
                f"Channel purpose '{purpose}' set to channel {channel.id} "
                f"by {ctx.author.id} in guild {ctx.guild.id}"
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting channel purpose: {e}", exc_info=True)
            await ctx.response.send_message(
                "Произошла ошибка при настройке канала",
                ephemeral=True
            )

    @commands.slash_command(
        name="list_channels",
        description="Показать все назначенные каналы сервера",
    )
    async def list_channels(
        self,
        ctx: disnake.ApplicationCommandInteraction,
    ) -> None:
        if not ctx.author.guild_permissions.administrator:
            logger.warning(f"Non-admin {ctx.author.id} attempted to use list_channels in guild {ctx.guild.id}")
            await ctx.response.send_message(
                "Только администраторы могут использовать эту команду",
                ephemeral=True,
            )
            return

        try:
            purposes = await self._channel_service.get_all_purposes(ctx.guild.id)

            purpose_labels = {
                "welcome": "Приветствие",
                "member_log": "Лог входа/выхода",
                "mod_log": "Лог модерации",
                "message_log": "Лог сообщений",
                "channel_log": "Лог каналов",
                "stream_announce": "Анонсы стримов",
                "dev_blog": "Dev Blog",
                "ai_moderation_log": "AI moderation log",
            }

            embed = disnake.Embed(
                title="Назначенные каналы",
                color=COLOR_BLUE,
            )

            if not purposes:
                embed.description = (
                    "Ни один канал не назначен.\n"
                    "Используй `/set_channel` для настройки."
                )
            else:
                lines = []
                for purpose_value, channel_id in purposes.items():
                    label = purpose_labels.get(purpose_value, purpose_value)
                    channel = ctx.guild.get_channel(channel_id)
                    ch_str = channel.mention if channel else f"(удалён, id={channel_id})"
                    lines.append(f"**{label}**: {ch_str}")

                configured = set(purposes.keys())
                missing_lines = []
                for p in ChannelPurpose:
                    if p.value not in configured:
                        label = purpose_labels.get(p.value, p.value)
                        missing_lines.append(f"**{label}**: не настроен")

                embed.description = "\n".join(lines)
                if missing_lines:
                    embed.add_field(
                        name="Не настроены",
                        value="\n".join(missing_lines),
                        inline=False,
                    )

            embed.set_footer(text="Используй /set_channel для изменения")
            await ctx.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Listed channel purposes for guild {ctx.guild.id} by {ctx.author.id}")
        except Exception as e:
            logger.error(f"Error listing channels for guild {ctx.guild.id}: {e}", exc_info=True)
            await ctx.response.send_message(
                "Произошла ошибка при получении списка каналов",
                ephemeral=True
            )


def setup(bot: commands.Bot) -> None:
    pass
