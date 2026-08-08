import disnake
from disnake.ext import commands
from typing import Optional

from application.schemas.moderation_schemas import BanCommandSchema, WarnCommandSchema, KickCommandSchema, ReasonSchema, UserIdSchema, MuteCommandSchema
from application.schemas.server_role_purpose_schemas import ServerRolePurposeSchema
from presentation.views.moderation_views import PunishmentListView
from application.services import (
    LoggingService,
    ModerationHistoryService,
    ModeratorService,
    ServerRolePurposeService,
)
from core.domain.server_role_purpose import ServerRolePurpose
from core.domain.value_objects import PunishmentType
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class ModerationCog(commands.Cog):
    def __init__(
        self,
        moderator_service: ModeratorService,
        history_service: ModerationHistoryService,
        logging_service: Optional[LoggingService] = None,
        server_role_purpose_service: Optional[ServerRolePurposeService] = None,
    ):
        self._moderator_service = moderator_service
        self._history_service = history_service
        self._logging_service = logging_service
        self._server_role_purpose_service = server_role_purpose_service

    def cog_load(self):
        logger.info("ModerationCog loaded")

    @commands.slash_command(name="moderation", description="Список команд модерации")
    async def moderation(self, ctx: disnake.ApplicationCommandInteraction):
        embed = disnake.Embed(
            title="Модерация",
            description=(
                "**Наказания:**\n"
                "`/warn` — предупреждение\n"
                "`/mute` — мут через модальное окно\n"
                "`/unmute` — снять мут\n"
                "`/kick` — кик\n"
                "`/ban` — бан\n"
                "`/unban` — разбан\n\n"
                "**Списки:**\n"
                "`/history` — история пользователя\n"
                "`/punishments` — активные наказания\n\n"
                "**Каналы и очистка:**\n"
                "`/slowmode` — slowmode канала\n"
                "`/purge` — массовое удаление сообщений\n\n"
                "**Context menu:**\n"
                "⚠️ Быстрое предупреждение\n"
                "🔇 Замутить\n"
                "📋 История пользователя"
            ),
            color=disnake.Color.blue(),
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(name="warn", description="Выдать варн пользователю")
    @commands.has_permissions(moderate_members=True)
    async def warn(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        reason: str = "Нарушение правил",
        duration: int = None,
    ):
        validated = self._validate(
            WarnCommandSchema,
            {"user": user, "reason": reason, "duration_seconds": duration},
        )

        async def action():
            return await self._moderator_service.warn_user(
                moderator=ctx.author,
                target=user,
                reason=validated.reason,
                duration_seconds=validated.duration_seconds,
            )

        await self._execute_moderation(ctx, "Warning issued", action)


    @commands.slash_command(name="mute", description="Выдать мут")
    @commands.has_permissions(ban_members=True)
    async def mute(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        duration: int = None,
        reason: str = "Нарушение правил"
    ):
        validated = self._validate(
            MuteCommandSchema,
            {"user": user, "reason": reason, "duration_seconds": duration},
        )

        async def action():
            return await self._moderator_service.mute_user(
                moderator=ctx.author,
                target=user,
                reason=validated.reason,
                duration_seconds=validated.duration_seconds,
            )

        await self._execute_moderation(ctx, "User muted", action)

    @commands.slash_command(name="unmute", description="Снять мут")
    @commands.has_permissions(moderate_members=True)
    async def unmute(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        reason: str = "Досрочное снятие мута",
    ):
        validated = self._validate(
            ReasonSchema,
            {"value": reason},
        )
        
        async def action():
            return await self._moderator_service.unmute_user(
                moderator=ctx.author,
                target=user,
                reason=validated.value,
            )

        await self._execute_moderation(ctx, "User unmuted", action)
     

    @commands.slash_command(name="kick", description="Кикнуть пользователя")
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        reason: str = "Нарушение правил",
    ):
        validated = self._validate(
            KickCommandSchema,
            {"user": user, "reason": reason},
        )
        
        async def action():
            return await self._moderator_service.kick_user(
                moderator=ctx.author,
                target=user,
                reason=validated.reason,
            )

        await self._execute_moderation(ctx, "User kicked", action)


    @commands.slash_command(name="ban", description="Забанить пользователя")
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user: disnake.User,
        reason: str = "Нарушение правил",
        delete_message_days: int = 1,
        duration: int = None,
    ):
        validated = self._validate(
            BanCommandSchema,
            {"user": user, "duration_seconds": duration, "reason": reason, "delete_message_days": delete_message_days},
        )
        
        async def action():
            return await self._moderator_service.ban_user(
                moderator=ctx.author,
                target=user,
                duration_seconds=validated.duration_seconds,
                delete_message_days=validated.delete_message_days,
                reason=validated.reason,
            )

        await self._execute_moderation(ctx, "User banned", action)

    @commands.slash_command(name="unban", description="Разбанить пользователя по ID")
    @commands.has_permissions(ban_members=True)
    async def unban(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        user_id: str,
        reason: str = "Дострочное снятие наказание",
    ):
        validated = self._validate(
            ReasonSchema,
            {"value": reason},
        )
        
        async def action():
            await self._moderator_service.unban_user(
                moderator=ctx.author,
                guild=ctx.guild,
                user_id=int(user_id),
                reason=validated.value,
            )

        await self._execute_moderation(ctx, "Warning issued", action)


    @commands.slash_command(name="history", description="История наказаний пользователя")
    @commands.has_permissions(moderate_members=True)
    async def history(self, ctx: disnake.ApplicationCommandInteraction, user: disnake.Member):
        await ctx.response.defer(ephemeral=True)

        rows = await self._history_service.get_user_history(
            user.id,
            ctx.guild.id,
            limit=10,
        )

        summary = await self._history_service.get_user_punishment_summary(
            user.id,
            ctx.guild.id,
        )

        embed = disnake.Embed(
            title=f"📜 History · {user.display_name}",
            color=disnake.Color.blurple(),
        )

        embed.add_field(
            name="📊 Summary",
            value=(
                f"🔢 Total: **{summary['total_count']}**\n"
                f"🟢 Active: **{summary['active_count']}**\n"
                f"⚠️ Warns: **{summary['warning_count']}**\n"
                f"🔇 Mutes: **{summary['mute_count']}**\n"
                f"👢 Kicks: **{summary['kick_count']}**\n"
                f"⛔ Bans: **{summary['ban_count']}**"
            ),
            inline=False,
        )

        if rows:
            history_text = "\n".join(
                f"• `#{row['id']}` "
                f"{self._format_type_icon(row['type'])} "
                f"{'🟢' if row.get('is_active') else '⚪'} "
                f"{row.get('reason', 'No reason')[:60]}"
                for row in rows[:10]
            )
        else:
            history_text = "No records found"

        embed.add_field(
            name="🗂 Recent entries",
            value=history_text,
            inline=False,
        )

        embed.set_footer(text=f"User ID: {user.id}")

        await ctx.edit_original_response(embed=embed)

    @commands.slash_command(name="punishments", description="Список активных наказаний")
    @commands.has_permissions(moderate_members=True)
    async def punishments(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        punishment_type: str = "all",
    ):
        await ctx.response.defer(ephemeral=True)

        valid_types = {p.value for p in PunishmentType}
        punishment_type_val = None if punishment_type == "all" else punishment_type

        if punishment_type_val and punishment_type_val not in valid_types:
            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title="Invalid type",
                    description="Unknown punishment type selected",
                    color=disnake.Color.red(),
                )
            )
            return

        rows = await self._history_service.list_active_punishments(
            ctx.guild.id,
            punishment_type_val,
            limit=25,
        )

        embed = disnake.Embed(
            title="🧾 Active punishments",
            color=disnake.Color.blurple(),
        )

        if not rows:
            embed.description = "✨ No active punishments found"
            await ctx.edit_original_response(embed=embed)
            return

        embed.description = (
            f"📊 Total active cases: **{len(rows)}**\n"
            "Select a case below to manage it."
        )

        await ctx.edit_original_response(
            embed=embed,
            view=PunishmentListView(
                self._history_service,
                rows,
                self._logging_service,
            ),
        )

    @commands.slash_command(name="slowmode", description="Включить или отключить slowmode канала")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        seconds: int,
    ):
        await ctx.response.defer(ephemeral=True)

        seconds = max(0, min(seconds, 21600))

        try:
            await channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode updated by {ctx.author} ({ctx.author.id})",
            )

        except Exception as exc:
            logger.exception(
                f"[SLOWMODE] Failed | channel={channel.id} "
                f"moderator={ctx.author.id} error={exc}"
            )

            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title="Slowmode error",
                    description="Failed to update channel slowmode",
                    color=disnake.Color.red(),
                )
            )
            return

        status = "disabled" if seconds == 0 else f"{seconds}s"

        await ctx.edit_original_response(
            embed=disnake.Embed(
                title="⏱ Slowmode updated",
                description=(
                    f"📢 Channel: {channel.mention}\n"
                    f"⚙️ Status: **{status}**"
                ),
                color=disnake.Color.green(),
            )
        )

    @commands.slash_command(name="purge", description="Массовое удаление сообщений")
    @commands.has_permissions(manage_messages=True)
    async def purge(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        amount: int,
        user: disnake.Member = None,
        contains: str = None,
    ):
        await ctx.response.defer(ephemeral=True)

        amount = max(1, min(amount, 100))

        deleted: list[disnake.Message] = []

        async for message in ctx.channel.history(limit=amount):
            if user and message.author.id != user.id:
                continue
            if contains and contains.lower() not in (message.content or "").lower():
                continue
            deleted.append(message)

        if not deleted:
            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title="🧹 Purge",
                    description="No messages matched filters",
                    color=disnake.Color.yellow(),
                )
            )
            return

        try:
            await ctx.channel.delete_messages(deleted)

            if self._logging_service:
                await self._logging_service.log_bulk_delete(
                    deleted,
                    ctx.channel,
                    deleted_by=ctx.author,
                )

        except Exception as exc:
            logger.exception(f"[PURGE] Failed in channel {ctx.channel.id}: {exc}")

            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title="Purge error",
                    description="Failed to delete messages",
                    color=disnake.Color.red(),
                )
            )
            return

        await ctx.edit_original_response(
            embed=disnake.Embed(
                title="🧹 Purge completed",
                description=(
                    f"🗑 Deleted: **{len(deleted)}** messages\n"
                    f"📍 Channel: {ctx.channel.mention}"
                ),
                color=disnake.Color.green(),
            )
        )

    @commands.user_command(name="📋 История пользователя")
    @commands.has_permissions(moderate_members=True)
    async def user_history(
        self,
        interaction: disnake.CmdInteraction,
        user: disnake.User,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild:
            await interaction.edit_original_response(
                embed=disnake.Embed(
                    title="📋 History",
                    description="This command works only in a server",
                    color=disnake.Color.red(),
                )
            )
            return

        member = guild.get_member(user.id)
        if not member:
            await interaction.edit_original_response(
                embed=disnake.Embed(
                    title="📋 History",
                    description="User not found in this server",
                    color=disnake.Color.red(),
                )
            )
            return

        rows = await self._history_service.get_user_history(
            member.id,
            guild.id,
            limit=10,
        )

        summary = await self._history_service.get_user_punishment_summary(
            member.id,
            guild.id,
        )

        embed = disnake.Embed(
            title=f"📜 History · {member.display_name}",
            color=disnake.Color.blurple(),
        )

        embed.add_field(
            name="📊 Summary",
            value=(
                f"🔢 Total: **{summary['total_count']}**\n"
                f"🟢 Active: **{summary['active_count']}**\n"
                f"⚠️ Warns: **{summary['warning_count']}**\n"
                f"🔇 Mutes: **{summary['mute_count']}**\n"
                f"👢 Kicks: **{summary['kick_count']}**\n"
                f"⛔ Bans: **{summary['ban_count']}**"
            ),
            inline=False,
        )

        embed.description = (
            "\n".join(
                f"• #{row['id']} {row['type']} · {row.get('reason', '')[:60]}"
                for row in rows
            )
            if rows
            else "No history found"
        )

        await interaction.edit_original_response(embed=embed)

    @commands.message_command(name="⚠️ Быстрое предупреждение")
    @commands.has_permissions(moderate_members=True)
    async def quick_warn(
        self,
        interaction: disnake.CmdInteraction,
        message: disnake.Message,
    ):
        await interaction.response.defer(ephemeral=True)

        member = interaction.guild.get_member(message.author.id) if interaction.guild else None

        if not member:
            await interaction.edit_original_response(
                embed=disnake.Embed(
                    title="⚠️ Quick warn",
                    description="User not found on server",
                    color=disnake.Color.red(),
                )
            )
            return

        result = await self._moderator_service.warn_user(
            moderator=interaction.author,
            target=member,
            reason="Quick warning from message context",
        )

        embed = disnake.Embed(
            title="⚠️ Warning issued",
            color=disnake.Color.orange(),
        )

        embed.description = (
            result.get("escalation")
            or f"User {member.mention} has been warned."
        )

        await interaction.edit_original_response(embed=embed)

    @commands.user_command(name="🔇 Замутить")
    @commands.has_permissions(moderate_members=True)
    async def quick_mute(
        self,
        interaction: disnake.CmdInteraction,
        user: disnake.User,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild:
            await interaction.edit_original_response(
                embed=disnake.Embed(
                    title="🔇 Quick mute",
                    description="This command works only in a server",
                    color=disnake.Color.red(),
                )
            )
            return

        member = guild.get_member(user.id)

        if not member:
            await interaction.edit_original_response(
                embed=disnake.Embed(
                    title="🔇 Quick mute",
                    description="User not found in this server",
                    color=disnake.Color.red(),
                )
            )
            return

        result = await self._moderator_service.mute_user(
            moderator=interaction.author,
            target=member,
            reason="Quick mute from context menu",
            duration_seconds=300,
        )

        embed = disnake.Embed(
            title="🔇 User muted",
            color=disnake.Color.blurple(),
        )

        embed.description = (
            result.get("escalation")
            or f"{member.mention} has been muted for 5 minutes."
        )

        await interaction.edit_original_response(embed=embed)

    @commands.slash_command(
        name="activity_role",
        description="Set a Discord role used by Muxivo DS Activity access",
    )
    @commands.has_permissions(administrator=True)
    async def set_activity_role(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        kind: str = commands.Param(
            description="Activity role type",
            choices={
                "streamer": ServerRolePurpose.ACTIVITY_STREAMER.value,
                "developer": ServerRolePurpose.ACTIVITY_DEVELOPER.value,
            },
        ),
        role: disnake.Role = commands.Param(description="Discord role"),
    ):
        if not self._server_role_purpose_service:
            await ctx.response.send_message(
                "Activity role service is not configured.",
                ephemeral=True,
            )
            return

        if role.is_default() or role.managed:
            await ctx.response.send_message(
                "This role cannot be used for Activity access.",
                ephemeral=True,
            )
            return

        if ctx.guild.me and ctx.guild.me.top_role.position <= role.position:
            await ctx.response.send_message(
                "Move the bot role above this role before using it in Activity.",
                ephemeral=True,
            )
            return

        purpose = ServerRolePurpose(kind)
        validated = self._validate(
            ServerRolePurposeSchema,
            {
                "guild_id": ctx.guild.id,
                "purpose": purpose,
                "role_id": role.id,
            },
        )

        await self._server_role_purpose_service.set_role(
            validated.guild_id,
            validated.purpose,
            validated.role_id,
        )

        await ctx.response.send_message(
            embed=disnake.Embed(
                title="Activity role updated",
                description=(
                    f"Type: **{validated.purpose.value}**\n"
                    f"Role: {role.mention}\n"
                    f"Role ID: `{role.id}`"
                ),
                color=disnake.Color.green(),
            ),
            ephemeral=True,
        )

    async def _execute_moderation(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        title: str,
        func,
    ):
        try:
            await ctx.response.defer(ephemeral=True)

            result = await func()
            if not self._is_successful_result(result):
                raise RuntimeError("Operation was rejected by moderation service")

            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title=title,
                    description="Operation completed successfully",
                    color=disnake.Color.green(),
                )
            )
            return result

        except Exception as e:
            logger.exception(f"[MODERATION] {title} failed: {e}")

            await ctx.edit_original_response(
                embed=disnake.Embed(
                    title="Error",
                    description=str(e),
                    color=disnake.Color.red(),
                )
            )

    def _validate(self, schema, data: dict):
        try:
            return schema.model_validate(data)
        except Exception as e:
            raise ValueError(str(e))

    @staticmethod
    def _is_successful_result(result) -> bool:
        if isinstance(result, dict) and "success" in result:
            return bool(result["success"])
        return result is not False
        
    def _format_type_icon(self, punishment_type: str) -> str:
        icons = {
            "WARN": "⚠️",
            "MUTE": "🔇",
            "KICK": "👢",
            "BAN": "⛔",
        }
        return icons.get(punishment_type.upper(), "❔")
