from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import disnake
from disnake.ext import commands, tasks

from application.dto.creator_alert_dto import CreatorAlertSubscriptionInput
from application.services.creator_alert_service import CreatorAlertService
from core.domain.creator_alert import (
    CreatorAlertKind,
    CreatorAlertSubscription,
    CreatorContentEvent,
    CreatorPlatform,
)
from infrastructure.api.url_parser import CreatorUrlParser
from infrastructure.config import get_config
from infrastructure.logging import get_logger
from presentation.embeds.creator_alert_embed import CreatorAlertEmbedBuilder

logger = get_logger(__name__)

STREAM_ANNOUNCE_REPEAT_INTERVAL = timedelta(hours=2)


class StreamsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, creator_alert_service: CreatorAlertService):
        self._bot = bot
        self._creator_alert_service = creator_alert_service
        self._fallback_event_ids: set[str] = set()
        self._published_stream_keys: dict[tuple[str, str, str, str], datetime] = {}
        self.monitor_creator_sources.change_interval(seconds=get_config().creator_alert_poll_interval_seconds)
        logger.info("StreamsCog initialized")

    def cog_load(self) -> None:
        self.monitor_creator_sources.start()
        logger.info("Creator alert monitor started interval_seconds=%s", self.monitor_creator_sources.seconds)

    def cog_unload(self) -> None:
        self.monitor_creator_sources.cancel()
        logger.info("Creator alert monitor stopped")

    @tasks.loop(seconds=180)
    async def monitor_creator_sources(self) -> None:
        logger.info("Running creator alert monitor")
        for guild in self._bot.guilds:
            subscriptions = await self._creator_alert_service.list_sources(guild.id)
            for subscription in subscriptions:
                try:
                    event = await self._creator_alert_service.check_subscription(subscription)
                    if not event or subscription.id is None:
                        continue
                    if self._is_recent_stream_publication(guild, event, "subscription_monitor"):
                        await self._creator_alert_service.mark_announced(subscription.id, event.event_id)
                        continue
                    await self._publish_subscription_event(guild, subscription, event)
                    await self._creator_alert_service.mark_announced(subscription.id, event.event_id)
                    self._remember_stream_publication(guild, event)
                except Exception as exc:
                    logger.error(
                        "Creator alert monitor failed guild_id=%s subscription_id=%s error=%s",
                        guild.id,
                        subscription.id,
                        exc,
                        exc_info=True,
                    )
            await self._scan_discord_streaming_members(guild)

    @monitor_creator_sources.before_loop
    async def before_monitor_creator_sources(self) -> None:
        await self._bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_presence_update(self, before: disnake.Member, after: disnake.Member) -> None:
        if before.bot or not after.guild:
            return
        before_stream = self._get_stream_activity(before)
        after_stream = self._get_stream_activity(after)
        if before_stream or not after_stream:
            return

        await self._handle_streaming_presence(after, after_stream, "presence_update")

    async def _scan_discord_streaming_members(self, guild: disnake.Guild) -> None:
        inspected = 0
        stream_count = 0
        for member in guild.members:
            if member.bot:
                continue
            inspected += 1
            stream = self._get_stream_activity(member)
            if not stream:
                continue
            stream_count += 1
            await self._handle_streaming_presence(member, stream, "presence_scan")
        logger.info(
            "Discord streaming activity scan completed guild_id=%s inspected=%s streams=%s",
            guild.id,
            inspected,
            stream_count,
        )

    async def _handle_streaming_presence(
        self,
        member: disnake.Member,
        stream: disnake.Streaming,
        reason: str,
    ) -> None:
        if not member.guild:
            return

        guild_sources = await self._creator_alert_service.list_sources(member.guild.id)
        subscriptions = [source for source in guild_sources if source.user_id == member.id]
        active_stream_sources = [
            source
            for source in subscriptions
            if source.active and source.alert_kind == CreatorAlertKind.STREAM
        ]
        configured_user_sources = [
            source
            for source in active_stream_sources
            if self._creator_alert_service.is_platform_configured(source.platform)
        ]
        event_platform = self._stream_platform(stream)
        configured_matching_sources = [
            source
            for source in guild_sources
            if source.active
            and source.alert_kind == CreatorAlertKind.STREAM
            and source.platform == event_platform
            and self._creator_alert_service.is_platform_configured(source.platform)
            and self._source_matches_stream(source, stream)
        ]
        if configured_user_sources or configured_matching_sources:
            logger.info(
                "Skipping Muxivo DS Activity fallback because configured source exists guild_id=%s user_id=%s sources=%s reason=%s",
                member.guild.id,
                member.id,
                [source.id for source in configured_user_sources or configured_matching_sources],
                reason,
            )
            return

        source = active_stream_sources[0] if active_stream_sources else None
        platform = source.platform if source else event_platform
        event = self._build_discord_stream_event(member, stream, platform)
        if self._is_recent_stream_publication(member.guild, event, reason):
            if source and source.id is not None:
                await self._creator_alert_service.mark_announced(source.id, event.event_id)
            return
        if event.event_id in self._fallback_event_ids or (source and source.last_event_id == event.event_id):
            logger.info(
                "Muxivo DS Activity fallback already announced guild_id=%s user_id=%s event_id=%s reason=%s",
                member.guild.id,
                member.id,
                event.event_id,
                reason,
            )
            return

        logger.info(
            "Discord streaming activity resolved guild_id=%s user_id=%s title=%s game=%s url=%s raw=%s reason=%s",
            member.guild.id,
            member.id,
            event.title,
            event.game,
            event.url,
            self._stream_payload(stream),
            reason,
        )
        if source:
            await self._publish_subscription_event(member.guild, source, event)
            if source.id is not None:
                await self._creator_alert_service.mark_announced(source.id, event.event_id)
        else:
            await self._publish_default_event(member.guild, member.id, event)
        self._fallback_event_ids.add(event.event_id)
        self._remember_stream_publication(member.guild, event)

    @commands.slash_command(name="streamer", description="Manage creator alert subscriptions")
    async def streamer(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        logger.info("Streamer command group invoked user_id=%s", ctx.author.id)

    @streamer.sub_command(name="add", description="Add a creator source")
    async def streamer_add(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        platform: str = commands.Param(choices=["twitch", "youtube", "kick"]),
        channel_url: str = commands.Param(max_length=2048),
        channel_name: str = commands.Param(default="", max_length=120),
    ) -> None:
        await ctx.response.defer(ephemeral=True)
        try:
            source = await self._creator_alert_service.save_source(
                CreatorAlertSubscriptionInput(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    platform=CreatorPlatform(platform),
                    channel_url=channel_url,
                    channel_name=channel_name or None,
                )
            )
        except ValueError as exc:
            await ctx.edit_original_response(content=str(exc))
            return

        embed = disnake.Embed(
            title="Creator source saved",
            description=f"{source.platform.value.title()} source connected for {source.channel_name or source.channel_url}.",
            color=disnake.Color.green(),
        )
        if await self._publish_source_if_live(ctx.guild, source, "streamer_add"):
            embed.description += "\nLive event was found and published to the stream announce channel."
        await ctx.edit_original_response(embed=embed)

    @streamer.sub_command(name="remove", description="Remove a creator source")
    async def streamer_remove(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        source_id: int,
    ) -> None:
        await ctx.response.defer(ephemeral=True)
        removed = await self._creator_alert_service.remove_source(ctx.guild.id, ctx.author.id, source_id)
        message = "Creator source removed" if removed else "Creator source was not found"
        await ctx.edit_original_response(content=message)

    @streamer.sub_command(name="list", description="List creator sources")
    async def streamer_list(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        await ctx.response.defer(ephemeral=True)
        is_admin = bool(ctx.author.guild_permissions.administrator)
        sources = await self._creator_alert_service.list_sources(
            ctx.guild.id,
            None if is_admin else ctx.author.id,
        )
        embed = disnake.Embed(title="Creator sources", color=0x5865F2)
        if not sources:
            embed.description = "No creator sources connected yet."
        for source in sources[:10]:
            embed.add_field(
                name=f"#{source.id} {source.platform.value.title()} / {source.alert_kind.value}",
                value=f"{source.channel_name or source.channel_url}\nActive: {source.active}",
                inline=False,
            )
        await ctx.edit_original_response(embed=embed)

    @commands.slash_command(name="stream-template", description="Manage creator alert embed templates")
    async def stream_template(self, ctx: disnake.ApplicationCommandInteraction) -> None:
        logger.info("Stream template command group invoked user_id=%s", ctx.author.id)

    @stream_template.sub_command(name="set", description="Set the default template for a creator source")
    async def stream_template_set(
        self,
        ctx: disnake.ApplicationCommandInteraction,
        source_id: int,
        title_template: str = commands.Param(default="{creator.name} начал стрим на {platform}", max_length=256),
        description_template: str = commands.Param(
            default="{creator.ping}\n\n**{creator.name} уже в эфире.**\n\n**Название:** {title}\n**Категория:** {game}\n\n{url}",
            max_length=2000,
        ),
        ping_role: disnake.Role | None = None,
    ) -> None:
        await ctx.response.defer(ephemeral=True)
        source = await self._creator_alert_service.get_source_for_user(ctx.guild.id, ctx.author.id, source_id)
        if not source:
            await ctx.edit_original_response(content="Creator source was not found")
            return
        saved = await self._creator_alert_service.save_source(
            CreatorAlertSubscriptionInput(
                guild_id=source.guild_id,
                user_id=source.user_id,
                platform=source.platform,
                channel_url=source.channel_url,
                channel_name=source.channel_name,
                external_channel_id=source.external_channel_id,
                alert_kind=source.alert_kind,
                title_template=title_template,
                description_template=description_template,
                button_label=source.button_label,
                color=source.color,
                ping_role_id=ping_role.id if ping_role else source.ping_role_id,
                active=source.active,
            )
        )
        embed = disnake.Embed(
            title="Stream template saved",
            description=f"Template updated for source #{saved.id}.",
            color=disnake.Color.green(),
        )
        await ctx.edit_original_response(embed=embed)

    async def _publish_subscription_event(
        self,
        guild: disnake.Guild,
        subscription: CreatorAlertSubscription,
        event: CreatorContentEvent,
    ) -> None:
        channel_id = await self._creator_alert_service.get_announce_channel_id(guild.id)
        channel = await self._resolve_text_channel(guild, channel_id)
        if not isinstance(channel, disnake.TextChannel):
            logger.warning("Stream announce channel is not configured guild_id=%s", guild.id)
            return

        ping_role_id = subscription.ping_role_id or await self._creator_alert_service.get_default_ping_role_id(guild.id)
        creator_ping = f"||<@&{ping_role_id}>||" if ping_role_id else f"<@{subscription.user_id}>"
        creator_icon_url = await self._member_avatar_url(guild, subscription.user_id)
        embed = CreatorAlertEmbedBuilder.build(
            event,
            title_template=subscription.title_template,
            description_template=subscription.description_template,
            color=CreatorAlertEmbedBuilder.platform_color(event.platform, subscription.color),
            creator_ping=creator_ping,
            creator_icon_url=creator_icon_url,
        )
        content = creator_ping if ping_role_id else ""
        await channel.send(
            content=content,
            embed=embed,
            components=self._stream_link_components(subscription.button_label, event.url),
            allowed_mentions=disnake.AllowedMentions(roles=True, users=False),
        )
        logger.info(
            "Published creator alert guild_id=%s subscription_id=%s event_id=%s",
            guild.id,
            subscription.id,
            event.event_id,
        )

    async def _publish_source_if_live(
        self,
        guild: disnake.Guild,
        subscription: CreatorAlertSubscription,
        reason: str,
    ) -> bool:
        # This keeps command-created sources responsive while the Activity panel still uses the scheduled monitor.
        if subscription.id is None:
            logger.warning("Creator alert immediate publish skipped because source id is missing reason=%s", reason)
            return False
        try:
            event = await self._creator_alert_service.check_subscription(subscription)
            if not event:
                logger.info(
                    "Creator alert immediate publish found no event guild_id=%s subscription_id=%s reason=%s",
                    guild.id,
                    subscription.id,
                    reason,
                )
                return False
            if self._is_recent_stream_publication(guild, event, reason):
                await self._creator_alert_service.mark_announced(subscription.id, event.event_id)
                return False
            await self._publish_subscription_event(guild, subscription, event)
            await self._creator_alert_service.mark_announced(subscription.id, event.event_id)
            self._remember_stream_publication(guild, event)
            logger.info(
                "Creator alert immediate publish completed guild_id=%s subscription_id=%s event_id=%s reason=%s",
                guild.id,
                subscription.id,
                event.event_id,
                reason,
            )
            return True
        except Exception as exc:
            logger.error(
                "Creator alert immediate publish failed guild_id=%s subscription_id=%s reason=%s error=%s",
                guild.id,
                subscription.id,
                reason,
                exc,
                exc_info=True,
            )
            return False

    async def _publish_default_event(
        self,
        guild: disnake.Guild,
        user_id: int,
        event: CreatorContentEvent,
    ) -> None:
        channel_id = await self._creator_alert_service.get_announce_channel_id(guild.id)
        channel = await self._resolve_text_channel(guild, channel_id)
        if not isinstance(channel, disnake.TextChannel):
            logger.warning("Default stream announce skipped because channel is missing guild_id=%s", guild.id)
            return
        ping_role_id = await self._creator_alert_service.get_default_ping_role_id(guild.id)
        content = f"||<@&{ping_role_id}>||" if ping_role_id else ""
        embed = CreatorAlertEmbedBuilder.build(
            event,
            title_template="",
            description_template="",
            color=CreatorAlertEmbedBuilder.platform_color(event.platform),
            creator_ping=f"<@{user_id}>",
            creator_icon_url=await self._member_avatar_url(guild, user_id),
        )
        await channel.send(
            content=content,
            embed=embed,
            components=self._stream_link_components("Watch", event.url),
            allowed_mentions=disnake.AllowedMentions(roles=True, users=False),
        )
        logger.info("Published Muxivo DS Activity fallback stream alert guild_id=%s user_id=%s", guild.id, user_id)

    def _stream_link_components(self, label: str, url: str) -> list[disnake.ui.Button]:
        if not url.startswith(("http://", "https://")):
            return []
        return [disnake.ui.Button(label=(label or "Watch")[:80], url=url)]

    def _is_recent_stream_publication(
        self,
        guild: disnake.Guild,
        event: CreatorContentEvent,
        reason: str,
    ) -> bool:
        key = self._stream_publication_key(guild, event)
        published_at = self._stream_publication_cache().get(key)
        if not published_at:
            return False
        if datetime.now(timezone.utc) - published_at >= STREAM_ANNOUNCE_REPEAT_INTERVAL:
            return False
        logger.info(
            "Creator alert stream publication skipped by cooldown guild_id=%s key=%s event_id=%s reason=%s",
            guild.id,
            key,
            event.event_id,
            reason,
        )
        return True

    def _remember_stream_publication(self, guild: disnake.Guild, event: CreatorContentEvent) -> None:
        now = datetime.now(timezone.utc)
        cache = self._stream_publication_cache()
        cache[self._stream_publication_key(guild, event)] = now
        stale_keys = [
            key
            for key, published_at in cache.items()
            if now - published_at >= STREAM_ANNOUNCE_REPEAT_INTERVAL * 2
        ]
        for key in stale_keys:
            cache.pop(key, None)

    def _stream_publication_cache(self) -> dict[tuple[str, str, str, str], datetime]:
        if not hasattr(self, "_published_stream_keys"):
            self._published_stream_keys = {}
        return self._published_stream_keys

    def _stream_publication_key(
        self,
        guild: disnake.Guild,
        event: CreatorContentEvent,
    ) -> tuple[str, str, str, str]:
        return (
            str(guild.id),
            event.alert_kind.value,
            event.platform.value,
            self._stream_identity(event.platform, event.url) or event.event_id,
        )

    def _source_matches_stream(
        self,
        source: CreatorAlertSubscription,
        activity: disnake.Streaming,
    ) -> bool:
        stream_identity = self._stream_identity(source.platform, self._stream_url(activity))
        source_identity = self._source_identity(source)
        return bool(stream_identity and source_identity and stream_identity == source_identity)

    def _source_identity(self, source: CreatorAlertSubscription) -> str | None:
        if source.platform == CreatorPlatform.TWITCH:
            return (source.external_channel_id or CreatorUrlParser.twitch_login(source.channel_url) or "").lower() or None
        if source.platform == CreatorPlatform.YOUTUBE:
            return CreatorUrlParser.youtube_channel_ref(source.external_channel_id or source.channel_url)
        if source.platform == CreatorPlatform.KICK:
            return (source.external_channel_id or source.channel_url).strip().lower() or None
        return None

    def _stream_identity(self, platform: CreatorPlatform, url: str) -> str | None:
        if platform == CreatorPlatform.TWITCH:
            return (CreatorUrlParser.twitch_login(url) or "").lower() or None
        if platform == CreatorPlatform.YOUTUBE:
            return self._youtube_video_id(url) or CreatorUrlParser.youtube_channel_ref(url)
        if platform == CreatorPlatform.KICK:
            return url.strip().lower() or None
        return url.strip().lower() or None

    def _build_discord_stream_event(
        self,
        member: disnake.Member,
        activity: disnake.Streaming,
        platform: CreatorPlatform,
    ) -> CreatorContentEvent:
        return CreatorContentEvent(
            platform=platform,
            alert_kind=CreatorAlertKind.STREAM,
            event_id=self._discord_activity_event_id(member, activity),
            creator_name=member.display_name,
            title=self._stream_title(activity),
            url=self._stream_url(activity),
            game=self._stream_game(activity),
            thumbnail_url=self._stream_thumbnail_url(activity),
        )

    def _discord_activity_event_id(self, member: disnake.Member, activity: disnake.Streaming) -> str:
        started_at = getattr(activity, "start", None) or getattr(activity, "created_at", None)
        if started_at:
            marker = int(started_at.timestamp())
        else:
            marker = self._stream_url(activity) or self._stream_title(activity)
        return f"discord-activity:{member.id}:{marker}"

    def _get_stream_activity(self, member: disnake.Member) -> disnake.Streaming | None:
        for activity in member.activities:
            if isinstance(activity, disnake.Streaming):
                return activity
        return None

    def _stream_title(self, activity: disnake.Streaming) -> str:
        return activity.name or activity.details or "Live stream"

    def _stream_game(self, activity: disnake.Streaming) -> str:
        return activity.game or "Not specified"

    def _stream_url(self, activity: disnake.Streaming) -> str:
        twitch_name = activity.twitch_name
        if twitch_name and "twitch.tv" not in activity.url:
            return f"https://www.twitch.tv/{twitch_name}"
        return activity.url or ""

    def _stream_platform(self, activity: disnake.Streaming) -> CreatorPlatform:
        url = self._stream_url(activity).lower()
        if "youtube.com" in url or "youtu.be" in url:
            return CreatorPlatform.YOUTUBE
        if "kick.com" in url:
            return CreatorPlatform.KICK
        if activity.twitch_name or "twitch.tv" in url:
            return CreatorPlatform.TWITCH
        return CreatorPlatform.TWITCH

    def _stream_thumbnail_url(self, activity: disnake.Streaming) -> str | None:
        thumbnail_url = (
            activity.large_image_link
            or activity.large_image_url
            or activity.small_image_link
            or activity.small_image_url
        )
        if thumbnail_url:
            return thumbnail_url
        youtube_video_id = self._youtube_video_id(activity.url or "")
        if youtube_video_id:
            return f"https://img.youtube.com/vi/{youtube_video_id}/maxresdefault.jpg"
        twitch_name = activity.twitch_name
        if not twitch_name and "twitch.tv" in (activity.url or "").lower():
            twitch_name = CreatorUrlParser.twitch_login(activity.url or "")
        if twitch_name:
            return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{twitch_name.lower()}-1280x720.jpg"
        return None

    def _youtube_video_id(self, url: str) -> str | None:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if "youtube.com" in host:
            return parse_qs(parsed.query).get("v", [None])[0]
        if "youtu.be" in host:
            return parsed.path.strip("/") or None
        return None

    def _stream_payload(self, activity: disnake.Streaming) -> dict:
        try:
            payload = activity.to_dict()
        except Exception:
            payload = {}
        payload["game"] = activity.game
        payload["platform"] = activity.platform
        payload["twitch_name"] = activity.twitch_name
        payload["thumbnail_url"] = self._stream_thumbnail_url(activity)
        return payload

    async def _member_avatar_url(self, guild: disnake.Guild, user_id: int) -> str | None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except Exception as exc:
                logger.warning(
                    "Failed to resolve creator avatar guild_id=%s user_id=%s error=%s",
                    guild.id,
                    user_id,
                    exc,
                )
                return None
        return member.display_avatar.url if member and member.display_avatar else None

    async def _resolve_text_channel(
        self,
        guild: disnake.Guild,
        channel_id: int | None,
    ) -> disnake.TextChannel | None:
        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)
        if isinstance(channel, disnake.TextChannel):
            return channel

        try:
            fetched = await self._bot.fetch_channel(channel_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch stream announce channel guild_id=%s channel_id=%s error=%s",
                guild.id,
                channel_id,
                exc,
            )
            return None
        return fetched if isinstance(fetched, disnake.TextChannel) else None
