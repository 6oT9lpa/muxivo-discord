from datetime import datetime, timedelta, timezone

import pytest
import disnake
from fastapi import HTTPException

import activity.server.dependencies as activity_dependencies
from activity.server.schemas.creator_alerts import CreatorAlertSourcePayload, CreatorAlertTestPayload
from activity.server.services.creator_alert_service import CreatorAlertService as ActivityCreatorAlertService
from activity.server.utils.creator_alert_messages import build_creator_alert_message
from application.dto.creator_alert_dto import CreatorAlertSubscriptionInput
from application.services.creator_alert_service import CreatorAlertService
from core.domain.creator_alert import CreatorAlertKind, CreatorAlertSubscription, CreatorContentEvent, CreatorPlatform
from infrastructure.api.twitch_client import TwitchClient
from infrastructure.api.url_parser import CreatorUrlParser
from infrastructure.api.youtube_client import YouTubeClient
from infrastructure.database import DatabaseManager
from infrastructure.database.repositories import ChannelConfigRepository, CreatorAlertRepository
from presentation.embeds.creator_alert_embed import CreatorAlertEmbedBuilder
from presentation.cogs.streams_cog import StreamsCog


class _RolePurposeService:
    async def get_role(self, guild_id, purpose):
        return 777


class _NoopClient:
    is_configured = True

    async def fetch_latest_event(self, channel_url, external_channel_id=None):
        return None


class _MissingCredentialsClient(_NoopClient):
    is_configured = False


class _VideoClient(_NoopClient):
    async def fetch_latest_event(self, channel_url, external_channel_id=None):
        return CreatorContentEvent(
            platform=CreatorPlatform.YOUTUBE,
            alert_kind=CreatorAlertKind.VIDEO,
            event_id="video-1",
            creator_name="Creator",
            title="New video",
            url="https://youtube.com/watch?v=video-1",
        )


class _LiveClient(_NoopClient):
    def __init__(self, event):
        self._event = event

    async def fetch_latest_event(self, channel_url, external_channel_id=None):
        return self._event


@pytest.fixture
def creator_event():
    return CreatorContentEvent(
        platform=CreatorPlatform.TWITCH,
        alert_kind=CreatorAlertKind.STREAM,
        event_id="evt-1",
        creator_name="Arnetik",
        title="Building Muxivo Discord",
        url="https://twitch.tv/arnetik",
        game="Minecraft",
    )


def test_creator_alert_preview_renders_extended_placeholders(creator_event):
    payload = CreatorAlertTestPayload(
        guild_id=100,
        platform="twitch",
        channel_name=creator_event.creator_name,
        channel_url=creator_event.url,
        title_template="{creator.name} on {platform}",
        description_template="{creator.ping} {game} {url} {title}",
        ping_role_id=777,
        game=creator_event.game,
    )

    message = build_creator_alert_message(payload)

    assert message["content"] == "||<@&777>||"
    assert message["embeds"][0]["title"] == "Arnetik on Twitch"
    assert "||<@&777>|| Minecraft https://twitch.tv/arnetik Preview alert" in message["embeds"][0]["description"]
    assert message["components"][0]["components"][0]["label"] == "Watch"
    assert message["components"][0]["components"][0]["url"] == "https://twitch.tv/arnetik"


def test_creator_url_parser_handles_twitch_and_youtube_urls():
    assert CreatorUrlParser.twitch_login("https://www.twitch.tv/stepiks_") == "stepiks_"
    assert CreatorUrlParser.twitch_login("stepiks_") == "stepiks_"
    assert CreatorUrlParser.youtube_channel_ref("https://www.youtube.com/@omni") == "@omni"
    assert CreatorUrlParser.youtube_channel_ref("https://www.youtube.com/channel/UC123") == "UC123"


def test_youtube_client_parses_video_urls_and_live_page():
    client = YouTubeClient("key")

    assert client._video_id("https://youtube.com/watch?v=bhu63w-yd9k") == "bhu63w-yd9k"
    assert client._video_id("https://youtu.be/bhu63w-yd9k") == "bhu63w-yd9k"
    assert client._video_id("https://youtube.com/live/bhu63w-yd9k?si=abc") == "bhu63w-yd9k"
    assert client._video_id("https://youtube.com/shorts/bhu63w-yd9k") == "bhu63w-yd9k"
    assert client._extract_video_id_from_page('{"videoId":"bhu63w-yd9k"}') == "bhu63w-yd9k"


def test_youtube_client_builds_live_event_from_video_payload():
    client = YouTubeClient("key")
    event = client._event_from_video_item(
        {
            "id": "bhu63w-yd9k",
            "snippet": {
                "channelTitle": "Creator",
                "title": "Live now",
                "liveBroadcastContent": "live",
                "thumbnails": {"high": {"url": "https://img.youtube.com/live.jpg"}},
            },
            "liveStreamingDetails": {"actualStartTime": "2026-07-03T00:00:00Z"},
        }
    )

    assert event.alert_kind == CreatorAlertKind.STREAM
    assert event.event_id == "bhu63w-yd9k"
    assert event.creator_name == "Creator"
    assert event.thumbnail_url == "https://img.youtube.com/live.jpg"


def test_youtube_client_builds_video_event_from_feed():
    client = YouTubeClient("key")
    event = client._event_from_feed(
        """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015"
              xmlns:media="http://search.yahoo.com/mrss/">
          <entry>
            <yt:videoId>video-1</yt:videoId>
            <title>Fresh video</title>
            <author><name>Creator</name></author>
            <media:group><media:thumbnail url="https://img.youtube.com/video.jpg" /></media:group>
          </entry>
        </feed>
        """
    )

    assert event is not None
    assert event.alert_kind == CreatorAlertKind.VIDEO
    assert event.event_id == "video-1"
    assert event.creator_name == "Creator"


def test_streaming_activity_game_uses_discord_state_not_title():
    cog = StreamsCog.__new__(StreamsCog)
    activity = disnake.Streaming(
        name="Twitch",
        details="Building Muxivo Discord",
        state="Minecraft",
        url="https://www.twitch.tv/stepiks_",
    )

    assert cog._stream_title(activity) == "Building Muxivo Discord"
    assert cog._stream_game(activity) == "Minecraft"
    assert cog._stream_url(activity) == "https://www.twitch.tv/stepiks_"
    assert cog._stream_thumbnail_url(activity).endswith("live_user_stepiks_-1280x720.jpg")


def test_youtube_streaming_activity_uses_youtube_platform_and_thumbnail():
    cog = StreamsCog.__new__(StreamsCog)
    activity = disnake.Streaming(
        name="YouTube",
        details="Моя трансляция",
        state="Not specified",
        url="https://youtube.com/watch?v=bhu63w-yd9k",
    )

    assert cog._stream_platform(activity) == CreatorPlatform.YOUTUBE
    assert cog._stream_thumbnail_url(activity) == "https://img.youtube.com/vi/bhu63w-yd9k/maxresdefault.jpg"


@pytest.mark.asyncio
async def test_streaming_activity_scan_publishes_existing_status_once():
    class Guild:
        id = 100
        members = []

    class Member:
        id = 42
        bot = False
        guild = Guild()
        display_name = "Creator"
        activities = [
            disnake.Streaming(
                name="Twitch",
                details="Building Muxivo Discord",
                state="Minecraft",
                url="https://www.twitch.tv/creator",
            )
        ]

    class Service:
        async def list_sources(self, guild_id, user_id=None):
            return []

    Guild.members = [Member()]
    cog = StreamsCog.__new__(StreamsCog)
    cog._creator_alert_service = Service()
    cog._fallback_event_ids = set()
    published = []

    async def publish_default(guild, user_id, event):
        published.append((guild.id, user_id, event))

    cog._publish_default_event = publish_default

    await cog._scan_discord_streaming_members(Guild())
    await cog._scan_discord_streaming_members(Guild())

    assert len(published) == 1
    assert published[0][0] == 100
    assert published[0][1] == 42
    assert published[0][2].title == "Building Muxivo Discord"
    assert published[0][2].game == "Minecraft"


@pytest.mark.asyncio
async def test_streaming_activity_fallback_skips_configured_matching_twitch_source():
    class Guild:
        id = 100

    class Member:
        id = 42
        bot = False
        guild = Guild()
        display_name = "Creator"

    class Service:
        async def list_sources(self, guild_id, user_id=None):
            return [
                CreatorAlertSubscription(
                    id=11,
                    guild_id=guild_id,
                    user_id=99,
                    platform=CreatorPlatform.TWITCH,
                    channel_url="https://www.twitch.tv/creator",
                    alert_kind=CreatorAlertKind.STREAM,
                )
            ]

        def is_platform_configured(self, platform):
            return True

    cog = StreamsCog.__new__(StreamsCog)
    cog._creator_alert_service = Service()
    cog._fallback_event_ids = set()
    cog._published_stream_keys = {}
    published = []

    async def publish_default(guild, user_id, event):
        published.append((guild.id, user_id, event.event_id))

    cog._publish_default_event = publish_default

    await cog._handle_streaming_presence(
        Member(),
        disnake.Streaming(
            name="Twitch",
            details="Building Muxivo Discord",
            state="Minecraft",
            url="https://www.twitch.tv/creator",
        ),
        "presence_update",
    )

    assert published == []


@pytest.mark.asyncio
async def test_immediate_source_publish_marks_live_event():
    subscription = CreatorAlertSubscriptionInput(
        guild_id=100,
        user_id=42,
        platform=CreatorPlatform.TWITCH,
        channel_url="https://twitch.tv/creator",
        channel_name="Creator",
    )
    event = CreatorContentEvent(
        platform=CreatorPlatform.TWITCH,
        alert_kind=CreatorAlertKind.STREAM,
        event_id="live-1",
        creator_name="Creator",
        title="Live now",
        url="https://twitch.tv/creator",
        game="Minecraft",
    )

    class Guild:
        id = 100

    class Service:
        def __init__(self):
            self.marked = []

        async def check_subscription(self, source):
            assert source.id == 11
            return event

        async def mark_announced(self, source_id, event_id):
            self.marked.append((source_id, event_id))

    service = Service()
    cog = StreamsCog.__new__(StreamsCog)
    cog._creator_alert_service = service
    published = []

    async def publish_subscription(guild, source, resolved_event):
        published.append((guild.id, source.id, resolved_event.event_id))

    cog._publish_subscription_event = publish_subscription
    source = CreatorAlertSubscription(
        id=11,
        guild_id=subscription.guild_id,
        user_id=subscription.user_id,
        platform=subscription.platform,
        channel_url=subscription.channel_url,
        channel_name=subscription.channel_name,
    )

    assert await cog._publish_source_if_live(Guild(), source, "test") is True
    assert published == [(100, 11, "live-1")]
    assert service.marked == [(11, "live-1")]


@pytest.mark.asyncio
async def test_creator_alert_service_respects_two_hour_repeat_cooldown(creator_event):
    service = CreatorAlertService(
        None,
        None,
        None,
        {CreatorPlatform.TWITCH: _LiveClient(creator_event)},
    )
    recent_subscription = CreatorAlertSubscription(
        id=1,
        guild_id=100,
        user_id=42,
        platform=CreatorPlatform.TWITCH,
        channel_url=creator_event.url,
        last_event_id="different-live-id",
        last_checked_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    due_subscription = CreatorAlertSubscription(
        id=2,
        guild_id=100,
        user_id=42,
        platform=CreatorPlatform.TWITCH,
        channel_url=creator_event.url,
        last_event_id=creator_event.event_id,
        last_checked_at=datetime.now(timezone.utc) - timedelta(hours=2, minutes=1),
    )

    assert await service.check_subscription(recent_subscription) is None
    assert await service.check_subscription(due_subscription) == creator_event


def test_default_creator_alert_embed_is_russian_and_visual(creator_event):
    event = CreatorContentEvent(
        platform=CreatorPlatform.TWITCH,
        alert_kind=CreatorAlertKind.STREAM,
        event_id="evt-2",
        creator_name="Gadj",
        title="я чемпион",
        url="https://www.twitch.tv/n1gadjiga",
        game="Minecraft",
        thumbnail_url="https://static-cdn.jtvnw.net/previews-ttv/live_user_gadj-1280x720.jpg",
    )

    embed = CreatorAlertEmbedBuilder.build(
        event,
        title_template="{creator.name} is live on {platform}",
        description_template="{creator.ping} {title}\nGame: {game}\n{url}",
        creator_ping="@stream ping",
        creator_icon_url="https://cdn.discordapp.com/avatars/1/avatar.png",
    )
    payload = embed.to_dict()

    assert payload["title"] == "Gadj начал стрим на Twitch"
    assert "уже в эфире" in payload["description"]
    assert "Категория" in payload["fields"][1]["name"]
    assert payload["author"]["icon_url"] == "https://cdn.discordapp.com/avatars/1/avatar.png"
    assert payload["image"]["url"].endswith("live_user_gadj-1280x720.jpg")
    assert payload["footer"]["icon_url"].endswith("live_user_gadj-1280x720.jpg")


def test_youtube_stream_embed_has_platform_specific_copy():
    event = CreatorContentEvent(
        platform=CreatorPlatform.YOUTUBE,
        alert_kind=CreatorAlertKind.STREAM,
        event_id="yt-live-1",
        creator_name="Санчеус",
        title="Моя трансляция",
        url="https://youtube.com/watch?v=bhu63w-yd9k",
        game="Just Chatting",
        thumbnail_url="https://img.youtube.com/vi/bhu63w-yd9k/maxresdefault.jpg",
    )

    embed = CreatorAlertEmbedBuilder.build(
        event,
        title_template="",
        description_template="",
        creator_ping="@stream ping",
    )
    payload = embed.to_dict()

    assert payload["title"] == "Санчеус начал стрим на YouTube"
    assert "прямой эфир на YouTube" in payload["description"]
    assert "ставь лайк" in payload["description"]
    assert payload["fields"][0]["value"] == "YouTube"
    assert payload["image"]["url"].endswith("bhu63w-yd9k/maxresdefault.jpg")


@pytest.mark.asyncio
async def test_platform_clients_skip_network_when_credentials_are_missing():
    twitch = TwitchClient(None, None)
    youtube = YouTubeClient(None)

    assert twitch.is_configured is False
    assert youtube.is_configured is False
    assert await twitch.fetch_latest_event("https://www.twitch.tv/stepiks_") is None
    assert await youtube.fetch_latest_event("https://www.youtube.com/@omni") is None


def test_creator_alert_service_reports_platform_configuration():
    db = DatabaseManager("postgresql://test:test@localhost:5432/test")
    service = CreatorAlertService(
        CreatorAlertRepository(db),
        ChannelConfigRepository(db),
        _RolePurposeService(),
        {
            CreatorPlatform.TWITCH: _MissingCredentialsClient(),
            CreatorPlatform.YOUTUBE: _NoopClient(),
        },
    )

    assert service.is_platform_configured(CreatorPlatform.TWITCH) is False
    assert service.is_platform_configured(CreatorPlatform.YOUTUBE) is True
    assert service.is_platform_configured(CreatorPlatform.KICK) is False


@pytest.mark.asyncio
async def test_creator_alert_service_filters_mismatched_event_kind():
    db = DatabaseManager("postgresql://test:test@localhost:5432/test")
    service = CreatorAlertService(
        CreatorAlertRepository(db),
        ChannelConfigRepository(db),
        _RolePurposeService(),
        {CreatorPlatform.YOUTUBE: _VideoClient()},
    )
    subscription = CreatorAlertSubscription(
        id=1,
        guild_id=100,
        user_id=42,
        platform=CreatorPlatform.YOUTUBE,
        channel_url="https://youtube.com/@creator",
        alert_kind=CreatorAlertKind.STREAM,
    )

    assert await service.check_subscription(subscription) is None


@pytest.mark.asyncio
async def test_creator_alert_service_enforces_five_sources_per_user(postgres_test_db):
    db = postgres_test_db
    try:
        repo = CreatorAlertRepository(db)
        channels = ChannelConfigRepository(db)
        service = CreatorAlertService(
            repo,
            channels,
            _RolePurposeService(),
            {CreatorPlatform.TWITCH: _NoopClient()},
        )

        for index in range(5):
            await service.save_source(
                CreatorAlertSubscriptionInput(
                    guild_id=100,
                    user_id=42,
                    platform=CreatorPlatform.TWITCH,
                    channel_url=f"https://twitch.tv/source{index}",
                )
            )

        with pytest.raises(ValueError):
            await service.save_source(
                CreatorAlertSubscriptionInput(
                    guild_id=100,
                    user_id=42,
                    platform=CreatorPlatform.YOUTUBE,
                    channel_url="https://youtube.com/@sixth",
                )
            )
    finally:
        pass


@pytest.mark.asyncio
async def test_activity_creator_alert_service_applies_default_ping_role(postgres_test_db, monkeypatch):
    db = postgres_test_db
    previous_db = activity_dependencies._db
    previous_role_service = activity_dependencies._role_purpose_service
    activity_dependencies._db = db
    activity_dependencies._role_purpose_service = _RolePurposeService()
    service = ActivityCreatorAlertService()

    async def ensure_access(*_):
        return {"id": "42", "username": "creator"}, {"is_admin": False, "is_streamer": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    try:
        saved = await service.save_source(
            CreatorAlertSourcePayload(
                guild_id=100,
                platform="twitch",
                channel_url="https://twitch.tv/creator",
                channel_name="Creator",
            ),
            "token",
        )

        assert saved["ping_role_id"] == "777"
        assert saved["user_id"] == "42"
    finally:
        activity_dependencies._db = previous_db
        activity_dependencies._role_purpose_service = previous_role_service


@pytest.mark.asyncio
async def test_activity_creator_alert_save_publishes_live_embed(postgres_test_db, monkeypatch):
    db = postgres_test_db
    previous_db = activity_dependencies._db
    previous_role_service = activity_dependencies._role_purpose_service
    activity_dependencies._db = db
    activity_dependencies._role_purpose_service = _RolePurposeService()
    await db.execute(
        """
        INSERT INTO server_channel_purposes (guild_id, purpose, channel_id)
        VALUES (?, ?, ?)
        """,
        (100, "stream_announce", 555),
    )
    await db.commit()
    service = ActivityCreatorAlertService()

    class LiveClient:
        is_configured = True

        async def fetch_latest_event(self, channel_url, external_channel_id=None):
            return CreatorContentEvent(
                platform=CreatorPlatform.TWITCH,
                alert_kind=CreatorAlertKind.STREAM,
                event_id="live-now",
                creator_name="Creator",
                title="Building Muxivo Discord",
                url=channel_url,
                game="Minecraft",
                thumbnail_url="https://static-cdn.jtvnw.net/previews-ttv/live_user_creator-1280x720.jpg",
            )

    class Discord:
        def __init__(self):
            self.requests = []

        async def safe_bot_request(self, method, path, *, params=None, json_body=None):
            self.requests.append((method, path, json_body))
            if method == "GET":
                return {"user": {"avatar": "avatar-hash"}}
            return {"id": "999"}

    async def ensure_access(*_):
        return {"id": "42", "username": "creator"}, {"is_admin": False, "is_streamer": True}

    discord = Discord()
    service._publish_service._discord = discord
    service._publish_service._platform_clients = {CreatorPlatform.TWITCH: LiveClient()}
    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    try:
        saved = await service.save_source(
            CreatorAlertSourcePayload(
                guild_id=100,
                platform="twitch",
                channel_url="https://twitch.tv/creator",
                channel_name="Creator",
                button_label="Смотреть",
            ),
            "token",
        )

        message_request = discord.requests[-1]
        assert message_request[0] == "POST"
        assert message_request[1] == "/channels/555/messages"
        assert message_request[2]["content"] == "||<@&777>||"
        assert message_request[2]["embeds"][0]["url"] == "https://twitch.tv/creator"
        assert message_request[2]["components"][0]["components"][0]["label"] == "Смотреть"
        reloaded = await db.fetch_one("SELECT last_event_id FROM creator_alert_subscriptions WHERE id = ?", (saved["id"],))
        assert reloaded["last_event_id"] == "live-now"
    finally:
        activity_dependencies._db = previous_db
        activity_dependencies._role_purpose_service = previous_role_service


@pytest.mark.asyncio
async def test_activity_creator_alert_service_updates_platform_and_restricts_creator_ping_role(postgres_test_db, monkeypatch):
    db = postgres_test_db
    previous_db = activity_dependencies._db
    previous_role_service = activity_dependencies._role_purpose_service
    activity_dependencies._db = db
    activity_dependencies._role_purpose_service = _RolePurposeService()
    service = ActivityCreatorAlertService()

    async def ensure_access(*_):
        return {"id": "42", "username": "creator"}, {"is_admin": False, "is_streamer": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    try:
        saved = await service.save_source(
            CreatorAlertSourcePayload(
                guild_id=100,
                platform="twitch",
                channel_url="https://twitch.tv/creator",
                channel_name="Creator",
                ping_role_id=999,
            ),
            "token",
        )
        await db.execute(
            "UPDATE creator_alert_subscriptions SET last_event_id = ?, last_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("old-event", saved["id"]),
        )
        await db.commit()
        updated = await service.save_source(
            CreatorAlertSourcePayload(
                guild_id=100,
                id=saved["id"],
                platform="youtube",
                channel_url="https://youtube.com/@creator",
                channel_name="Creator",
                ping_role_id=999,
            ),
            "token",
        )

        assert updated["platform"] == "youtube"
        assert updated["ping_role_id"] == "777"
        assert updated["last_event_id"] is None
        assert updated["last_checked_at"] is None
    finally:
        activity_dependencies._db = previous_db
        activity_dependencies._role_purpose_service = previous_role_service


@pytest.mark.asyncio
async def test_activity_creator_alert_delete_reports_missing_and_removes_owned_source(postgres_test_db, monkeypatch):
    db = postgres_test_db
    previous_db = activity_dependencies._db
    previous_role_service = activity_dependencies._role_purpose_service
    activity_dependencies._db = db
    activity_dependencies._role_purpose_service = _RolePurposeService()
    service = ActivityCreatorAlertService()

    async def ensure_access(*_):
        return {"id": "42", "username": "creator"}, {"is_admin": False, "is_streamer": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    try:
        saved = await service.save_source(
            CreatorAlertSourcePayload(
                guild_id=100,
                platform="twitch",
                channel_url="https://twitch.tv/creator",
                channel_name="Creator",
            ),
            "token",
        )

        missing = saved["id"] + 100
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_source(100, missing, "token")
        assert exc_info.value.status_code == 404

        deleted = await service.delete_source(100, saved["id"], "token")
        assert deleted == {"deleted": True, "id": saved["id"]}
        row = await db.fetch_one("SELECT id FROM creator_alert_subscriptions WHERE id = ?", (saved["id"],))
        assert row is None
    finally:
        activity_dependencies._db = previous_db
        activity_dependencies._role_purpose_service = previous_role_service


def test_activity_creator_alert_preview_uses_styled_embed_button_and_spoiler_ping():
    message = build_creator_alert_message(
        CreatorAlertTestPayload(
            guild_id=100,
            platform="youtube",
            channel_name="Creator",
            channel_url="https://youtube.com/watch?v=bhu63w-yd9k",
            ping_role_id=777,
            button_label="Watch live",
        )
    )

    assert message["content"] == "||<@&777>||"
    assert message["embeds"][0]["fields"][0]["value"] == "YouTube"
    assert "прямой эфир на YouTube" in message["embeds"][0]["description"]
    assert message["embeds"][0]["image"]["url"].endswith("bhu63w-yd9k/maxresdefault.jpg")
    assert message["components"][0]["components"][0]["label"] == "Watch live"


@pytest.mark.asyncio
async def test_activity_creator_alert_service_rejects_sixth_source(postgres_test_db, monkeypatch):
    db = postgres_test_db
    previous_db = activity_dependencies._db
    previous_role_service = activity_dependencies._role_purpose_service
    activity_dependencies._db = db
    activity_dependencies._role_purpose_service = _RolePurposeService()
    service = ActivityCreatorAlertService()

    async def ensure_access(*_):
        return {"id": "42", "username": "creator"}, {"is_admin": False, "is_streamer": True}

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    try:
        for index in range(5):
            await service.save_source(
                CreatorAlertSourcePayload(
                    guild_id=100,
                    platform="twitch",
                    channel_url=f"https://twitch.tv/creator{index}",
                ),
                "token",
            )

        with pytest.raises(HTTPException) as exc_info:
            await service.save_source(
                CreatorAlertSourcePayload(
                    guild_id=100,
                    platform="youtube",
                    channel_url="https://youtube.com/@sixth",
                ),
                "token",
            )
        assert exc_info.value.status_code == 400
    finally:
        activity_dependencies._db = previous_db
        activity_dependencies._role_purpose_service = previous_role_service
