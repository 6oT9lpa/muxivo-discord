from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

from core.domain.creator_alert import (
    CreatorAlertKind,
    CreatorContentEvent,
    CreatorPlatform,
)
from core.interfaces.clients import CreatorPlatformClientInterface
from infrastructure.api.url_parser import CreatorUrlParser
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class YouTubeClient(CreatorPlatformClientInterface):
    def __init__(self, api_key: Optional[str], proxy_url: Optional[str] = None):
        self._api_key = api_key
        self._proxy_url = proxy_url
        self._channel_id_cache: dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def fetch_latest_event(
        self,
        channel_url: str,
        external_channel_id: Optional[str] = None,
    ) -> Optional[CreatorContentEvent]:
        if not self.is_configured:
            logger.info("YouTube API key is not configured")
            return None

        direct_video_id = self._video_id(channel_url) or self._video_id(external_channel_id or "")
        if direct_video_id:
            return await self._fetch_video_event(direct_video_id)

        channel_ref = external_channel_id or CreatorUrlParser.youtube_channel_ref(channel_url)
        channel_id = await self._resolve_channel_id(channel_ref)
        if not channel_id:
            logger.warning("Unable to resolve YouTube channel ref=%s", channel_ref)
            return None

        live_event = await self._fetch_channel_live_event(channel_ref, channel_id)
        if live_event:
            return live_event
        latest_event = await self._fetch_latest_feed_event(channel_id)
        if latest_event:
            return latest_event
        return await self._search(channel_id, event_type="live")

    async def _resolve_channel_id(self, channel_ref: str) -> Optional[str]:
        if channel_ref in self._channel_id_cache:
            logger.info("YouTube channel id cache hit ref=%s", channel_ref)
            return self._channel_id_cache[channel_ref]
        if channel_ref.startswith("UC"):
            self._channel_id_cache[channel_ref] = channel_ref
            return channel_ref
        if not channel_ref.startswith("@"):
            return channel_ref

        handle = channel_ref[1:]
        async with aiohttp.ClientSession() as session:
            logger.info("Resolving YouTube handle with channels.list handle=%s", channel_ref)
            async with session.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "id,snippet",
                    "forHandle": handle,
                    "key": self._api_key,
                },
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status < 400:
                    payload = await response.json()
                    items = payload.get("items") or []
                    if items:
                        channel_id = items[0]["id"]
                        self._channel_id_cache[channel_ref] = channel_id
                        return channel_id
                await self._log_api_error(response, "YouTube channels.list handle resolve failed")

        async with aiohttp.ClientSession() as session:
            logger.info("Resolving YouTube handle with search fallback handle=%s", channel_ref)
            async with session.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": channel_ref,
                    "type": "channel",
                    "maxResults": 1,
                    "key": self._api_key,
                },
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    await self._log_api_error(response, "YouTube channel resolve failed")
                    return None
                payload = await response.json()
        items = payload.get("items") or []
        if not items:
            return None
        channel_id = items[0]["snippet"]["channelId"]
        self._channel_id_cache[channel_ref] = channel_id
        return channel_id

    async def _fetch_channel_live_event(
        self,
        channel_ref: str,
        channel_id: str,
    ) -> Optional[CreatorContentEvent]:
        video_id = await self._fetch_live_video_id_from_page(self._channel_live_url(channel_ref, channel_id))
        if not video_id:
            logger.info("YouTube channel live page has no live video channel_id=%s", channel_id)
            return None
        event = await self._fetch_video_event(video_id)
        if event and event.alert_kind == CreatorAlertKind.STREAM:
            return event
        logger.info("YouTube live page video is not currently live channel_id=%s video_id=%s", channel_id, video_id)
        return None

    async def _fetch_live_video_id_from_page(self, url: str) -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            logger.info("Fetching YouTube live page url=%s", url)
            async with session.get(
                url,
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0 Muxivo Discord/1.0"},
            ) as response:
                if response.status >= 400:
                    logger.warning("YouTube live page request failed status=%s url=%s", response.status, url)
                    return None
                page = await response.text()
        return self._extract_video_id_from_page(page)

    async def _fetch_video_event(self, video_id: str) -> Optional[CreatorContentEvent]:
        async with aiohttp.ClientSession() as session:
            logger.info("Fetching YouTube video details video_id=%s", video_id)
            async with session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,liveStreamingDetails",
                    "id": video_id,
                    "key": self._api_key,
                },
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    await self._log_api_error(response, "YouTube videos.list failed")
                    return None
                payload = await response.json()
        items = payload.get("items") or []
        if not items:
            logger.info("YouTube video was not found video_id=%s", video_id)
            return None
        return self._event_from_video_item(items[0])

    async def _fetch_latest_feed_event(self, channel_id: str) -> Optional[CreatorContentEvent]:
        async with aiohttp.ClientSession() as session:
            logger.info("Fetching YouTube RSS feed channel_id=%s", channel_id)
            async with session.get(
                "https://www.youtube.com/feeds/videos.xml",
                params={"channel_id": channel_id},
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    logger.warning("YouTube RSS feed request failed status=%s channel_id=%s", response.status, channel_id)
                    return None
                body = await response.text()
        return self._event_from_feed(body)

    async def _search(
        self,
        channel_id: str,
        event_type: Optional[str],
    ) -> Optional[CreatorContentEvent]:
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 1,
            "key": self._api_key,
        }
        if event_type:
            params["eventType"] = event_type

        async with aiohttp.ClientSession() as session:
            logger.info("Fetching YouTube event channel_id=%s event_type=%s", channel_id, event_type or "latest")
            async with session.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                proxy=self._proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    await self._log_api_error(response, "YouTube search failed")
                    return None
                payload = await response.json()

        items = payload.get("items") or []
        if not items:
            return None
        item = items[0]
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        thumbnails = snippet.get("thumbnails") or {}
        image = thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        is_live = event_type == "live" or snippet.get("liveBroadcastContent") == "live"
        return CreatorContentEvent(
            platform=CreatorPlatform.YOUTUBE,
            alert_kind=CreatorAlertKind.STREAM if is_live else CreatorAlertKind.VIDEO,
            event_id=video_id,
            creator_name=snippet.get("channelTitle") or "YouTube",
            title=snippet.get("title") or "New YouTube publication",
            url=f"https://www.youtube.com/watch?v={video_id}",
            thumbnail_url=image.get("url"),
        )

    def _channel_live_url(self, channel_ref: str, channel_id: str) -> str:
        if channel_ref.startswith("@"):
            return f"https://www.youtube.com/{channel_ref}/live"
        return f"https://www.youtube.com/channel/{channel_id}/live"

    def _video_id(self, value: str) -> Optional[str]:
        if not value:
            return None
        parsed = urlparse(value)
        host = parsed.netloc.lower()
        parts = [part for part in parsed.path.split("/") if part]
        if "youtu.be" in host and parts:
            return parts[0]
        if "youtube.com" not in host:
            return None
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        if len(parts) >= 2 and parts[0].lower() in {"live", "shorts", "embed"}:
            return parts[1]
        return None

    def _extract_video_id_from_page(self, page: str) -> Optional[str]:
        patterns = (
            r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{6,})"',
            r'watch\?v=([a-zA-Z0-9_-]{6,})',
            r'"canonicalBaseUrl"\s*:\s*"/watch\?v=([a-zA-Z0-9_-]{6,})"',
        )
        for pattern in patterns:
            match = re.search(pattern, page)
            if match:
                return html.unescape(match.group(1))
        return None

    def _event_from_video_item(self, item: dict) -> CreatorContentEvent:
        video_id = item["id"]
        snippet = item.get("snippet") or {}
        details = item.get("liveStreamingDetails") or {}
        thumbnails = snippet.get("thumbnails") or {}
        image = thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}
        is_live = snippet.get("liveBroadcastContent") == "live" or (
            bool(details.get("actualStartTime")) and not details.get("actualEndTime")
        )
        return CreatorContentEvent(
            platform=CreatorPlatform.YOUTUBE,
            alert_kind=CreatorAlertKind.STREAM if is_live else CreatorAlertKind.VIDEO,
            event_id=video_id,
            creator_name=snippet.get("channelTitle") or "YouTube",
            title=snippet.get("title") or "YouTube publication",
            url=f"https://www.youtube.com/watch?v={video_id}",
            thumbnail_url=image.get("url") or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        )

    def _event_from_feed(self, body: str) -> Optional[CreatorContentEvent]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            logger.warning("YouTube RSS feed parse failed error=%s", exc)
            return None
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/",
        }
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None
        video_id = self._xml_text(entry, "yt:videoId", ns)
        if not video_id:
            return None
        title = self._xml_text(entry, "atom:title", ns) or "YouTube publication"
        author = entry.find("atom:author/atom:name", ns)
        media_group = entry.find("media:group", ns)
        thumbnail = media_group.find("media:thumbnail", ns).get("url") if media_group is not None and media_group.find("media:thumbnail", ns) is not None else None
        return CreatorContentEvent(
            platform=CreatorPlatform.YOUTUBE,
            alert_kind=CreatorAlertKind.VIDEO,
            event_id=video_id,
            creator_name=author.text if author is not None and author.text else "YouTube",
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            thumbnail_url=thumbnail or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        )

    def _xml_text(self, element: ET.Element, path: str, namespaces: dict[str, str]) -> Optional[str]:
        found = element.find(path, namespaces)
        return found.text if found is not None else None

    async def _log_api_error(self, response: aiohttp.ClientResponse, message: str) -> None:
        body = await response.text()
        logger.warning("%s status=%s body=%s", message, response.status, body[:500])
