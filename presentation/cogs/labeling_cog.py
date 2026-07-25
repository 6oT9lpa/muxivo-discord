import disnake
from disnake.ext import commands

from application.services.moderation_labeling_service import ModerationLabelingService
from infrastructure.logging import get_logger
from presentation.embeds.base import DEFAULT_COLORS, EmbedBuilder
from presentation.views.labeling_guild_selection_view import LabelingGuildSelectionView

logger = get_logger(__name__)


class LabelingCog(commands.Cog):
    """DM-only administration and manual labels for trusted guilds."""

    def __init__(self, bot: commands.Bot, service: ModerationLabelingService, owner_id: int) -> None:
        self._bot = bot
        self._service = service
        self._owner_id = owner_id

    @commands.slash_command(
        name="labeling",
        description="Manage manual moderation labels in direct messages",
        contexts=disnake.InteractionContextTypes(bot_dm=True),
    )
    async def labeling(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        """Reject a bare invocation with an explicit, private explanation."""
        if not await self._require_dm(ctx):
            return
        await self._respond(ctx, "Choose a labeling action", "Use a /labeling subcommand to manage trust, roles, or labels.")

    @labeling.sub_command(name="manage", description="Open the private server-selection interface")
    async def manage(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        if not await self._require_dm_owner(ctx):
            return
        view = LabelingGuildSelectionView(self._service, ctx.author.id, list(self._bot.guilds))
        await ctx.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    @labeling.sub_command(name="trust", description="Enable or disable a guild for manual labeling")
    async def trust(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str, enabled: bool) -> None:
        if not await self._require_dm_owner(ctx):
            return
        guild = self._parse_snowflake(guild_id)
        if guild is None:
            await self._respond(ctx, "Invalid guild", "Guild ID must be a Discord snowflake.", error=True)
            return
        try:
            await self._service.set_trusted(ctx.author.id, guild, enabled)
        except PermissionError:
            await self._respond(ctx, "Labeling access denied", "Only the trusted owner can change trusted guilds.", error=True)
            return
        await self._respond(ctx, "Labeling updated", "Guild trust setting updated.")

    @trust.autocomplete("guild_id")
    async def trust_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    @labeling.sub_command(name="ai-metrics", description="Grant a trusted guild access to private AI moderator metrics")
    async def ai_metrics(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str, enabled: bool) -> None:
        if not await self._require_dm(ctx):
            return
        guild = self._parse_snowflake(guild_id)
        if guild is None:
            await self._respond(ctx, "Invalid guild", "Guild ID must be a Discord snowflake.", error=True)
            return
        try:
            await self._service.set_ai_metrics_access(ctx.author.id, guild, enabled)
        except PermissionError:
            await self._respond(ctx, "Metrics access denied", "Only the owner or a trusted guild ADMIN can change this setting.", error=True)
            return
        await self._respond(ctx, "AI metrics updated", "Private AI moderator metrics access was updated.")

    @ai_metrics.autocomplete("guild_id")
    async def ai_metrics_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    @labeling.sub_command(name="role", description="Grant or revoke an ADMIN or LABELER role")
    async def role(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str, user_id: str, role: str, enabled: bool) -> None:
        if not await self._require_dm(ctx):
            return
        guild = self._parse_snowflake(guild_id)
        user = self._parse_snowflake(user_id)
        normalized_role = role.upper()
        if guild is None or user is None or normalized_role not in {"ADMIN", "LABELER"}:
            await self._respond(ctx, "Invalid assignment", "Provide valid guild/user IDs and role ADMIN or LABELER.", error=True)
            return
        if not await self._member_exists(ctx, guild, user):
            return
        try:
            await self._service.set_role(ctx.author.id, guild, user, normalized_role, enabled)
        except PermissionError:
            await self._respond(ctx, "Labeling access denied", "You cannot manage this guild's labeling roles.", error=True)
            return
        await self._respond(ctx, "Labeling updated", "Labeling role updated.")

    @role.autocomplete("guild_id")
    async def role_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    @labeling.sub_command(name="add", description="Add a manual label to a message")
    async def add(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str, channel_id: str, message_id: str, author_id: str, label: str, comment: str = "") -> None:
        if not await self._require_dm(ctx):
            return
        values = [self._parse_snowflake(value) for value in (guild_id, channel_id, message_id, author_id)]
        if any(value is None for value in values):
            await self._respond(ctx, "Invalid message", "Guild, channel, message and author IDs must be Discord snowflakes.", error=True)
            return
        message = await self._resolve_message(ctx, values[0], values[1], values[2])
        if message is None:
            return
        if message.author.bot:
            await self._respond(ctx, "Invalid message", "Bot messages cannot be added to the manual-label dataset.", error=True)
            return
        if message.author.id != values[3]:
            await self._respond(ctx, "Invalid message", "The supplied author ID does not match the Discord message.", error=True)
            return
        try:
            created = await self._service.label(
                ctx.author.id,
                values[0],
                values[1],
                values[2],
                values[3],
                label,
                comment or None,
                snapshot=self._build_snapshot(message),
            )
        except PermissionError:
            await self._respond(ctx, "Labeling access denied", "You cannot label messages in this guild.", error=True)
            return
        except ValueError:
            await self._respond(ctx, "Invalid label", "The label must be a non-empty value.", error=True)
            return
        await self._respond(ctx, "Label added" if created else "Label unchanged", "Label added." if created else "This active label already exists.")

    @add.autocomplete("guild_id")
    async def add_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    @labeling.sub_command(name="revoke", description="Revoke your manual label from a message")
    async def revoke(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str, message_id: str, label: str) -> None:
        if not await self._require_dm(ctx):
            return
        guild = self._parse_snowflake(guild_id)
        message = self._parse_snowflake(message_id)
        if guild is None or message is None:
            await self._respond(ctx, "Invalid message", "Guild and message IDs must be Discord snowflakes.", error=True)
            return
        try:
            revoked = await self._service.revoke(ctx.author.id, guild, message, label)
        except PermissionError:
            await self._respond(ctx, "Labeling access denied", "You cannot revoke labels in this guild.", error=True)
            return
        await self._respond(ctx, "Label revoked" if revoked else "Label not found", "Label revoked." if revoked else "No active label created by you was found.")

    @revoke.autocomplete("guild_id")
    async def revoke_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    @labeling.sub_command(name="assignments", description="Show current labeling assignments for a trusted guild")
    async def assignments(self, ctx: disnake.ApplicationCommandInteraction, guild_id: str) -> None:
        if not await self._require_dm(ctx):
            return
        guild = self._parse_snowflake(guild_id)
        if guild is None:
            await self._respond(ctx, "Invalid guild", "Guild ID must be a Discord snowflake.", error=True)
            return
        try:
            assignments = await self._service.list_roles(ctx.author.id, guild)
        except PermissionError:
            await self._respond(ctx, "Labeling access denied", "You cannot view assignments for this guild.", error=True)
            return
        description = "\n".join(f"<@{item['user_id']}> — {item['role']}" for item in assignments) or "No assignments."
        await self._respond(ctx, "Labeling assignments", description)

    @assignments.autocomplete("guild_id")
    async def assignments_guild_autocomplete(self, _: disnake.ApplicationCommandInteraction, user_input: str) -> dict[str, str]:
        return self._guild_choices(user_input)

    async def _require_dm(self, ctx: disnake.ApplicationCommandInteraction) -> bool:
        if ctx.guild is None:
            return True
        logger.warning("Guild labeling command rejected guild_id=%s actor_id=%s", ctx.guild_id, ctx.author.id)
        await self._respond(ctx, "DM required", "For privacy, use this command in a direct message with the bot.", error=True)
        return False

    async def _require_dm_owner(self, ctx: disnake.ApplicationCommandInteraction) -> bool:
        if not await self._require_dm(ctx):
            return False
        if self._owner_id is not None and ctx.author.id == self._owner_id:
            return True
        await self._respond(ctx, "Labeling access denied", "Only the configured bot owner can change trusted guilds.", error=True)
        return False

    @staticmethod
    def _parse_snowflake(value: str) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _guild_choices(self, user_input: str) -> dict[str, str]:
        """Return Discord's bounded autocomplete list for guild-selection fields.

        Discord accepts at most 25 autocomplete entries. Values remain raw
        snowflakes so command handlers retain their existing validation path.
        """
        query = user_input.strip().casefold()
        guilds = sorted(self._bot.guilds, key=lambda guild: (guild.name.casefold(), guild.id))
        filtered = (
            guild for guild in guilds
            if not query or query in guild.name.casefold() or query in str(guild.id)
        )
        return {f"{guild.name} ({guild.id})": str(guild.id) for guild in list(filtered)[:25]}

    async def _resolve_message(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        guild_id: int,
        channel_id: int,
        message_id: int,
    ) -> disnake.Message | None:
        guild = self._bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id) if guild is not None else None
        if guild is None or channel is None or not hasattr(channel, "fetch_message"):
            await self._respond(ctx, "Message unavailable", "The bot cannot access that guild or channel.", error=True)
            return None
        try:
            return await channel.fetch_message(message_id)
        except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
            logger.warning("Manual label message unavailable guild_id=%s channel_id=%s message_id=%s", guild_id, channel_id, message_id)
            await self._respond(ctx, "Message unavailable", "The message was deleted or cannot be read by the bot.", error=True)
            return None

    async def _member_exists(self, ctx: disnake.ApplicationCommandInteraction, guild_id: int, user_id: int) -> bool:
        guild = self._bot.get_guild(guild_id)
        if guild is None:
            await self._respond(ctx, "Guild unavailable", "The bot cannot access that server.", error=True)
            return False
        if guild.get_member(user_id) is not None:
            return True
        try:
            await guild.fetch_member(user_id)
            return True
        except (disnake.NotFound, disnake.Forbidden, disnake.HTTPException):
            logger.info("Labeling role target unavailable guild_id=%s user_id=%s", guild_id, user_id)
            await self._respond(ctx, "User unavailable", "That user is not available in the selected server.", error=True)
            return False

    @staticmethod
    def _build_snapshot(message: disnake.Message) -> str:
        parts = [message.content]
        parts.extend(f"attachment:{attachment.filename} {attachment.url}" for attachment in message.attachments)
        parts.extend(f"embed:{embed.url or ''} {embed.description or ''}" for embed in message.embeds)
        return "\n".join(part for part in parts if part).strip()[:8_000]

    @staticmethod
    async def _respond(ctx: disnake.ApplicationCommandInteraction, title: str, description: str, *, error: bool = False) -> None:
        color = DEFAULT_COLORS["moderation"] if error else DEFAULT_COLORS["success"]
        embed = EmbedBuilder(color=color).set_title(title).set_description(description).build()
        # A failed authorization can be discovered after another layer has
        # already acknowledged the interaction. Falling back to follow-up
        # keeps the denial visible instead of raising InteractionResponded.
        if ctx.response.is_done():
            await ctx.followup.send(embed=embed, ephemeral=True)
        else:
            await ctx.response.send_message(embed=embed, ephemeral=True)
