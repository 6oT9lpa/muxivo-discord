from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from html import unescape
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import urlparse
import re

from application.dto.media_attachment_request import MediaAttachmentRequest


class DiscordAttachment(Protocol):
    """Minimal Discord attachment contract kept outside the Cog/UI layer."""

    id: int
    url: str
    filename: str
    content_type: str | None
    size: int
    width: int | None
    height: int | None


class DiscordMediaAttachmentNormalizer:
    """Converts Discord attachment metadata into the Core media API contract.

    Discord's ``content_type`` is optional, so a recognised filename suffix is
    used only as a fallback. Core still validates the downloaded bytes.
    """

    _IMAGE_MIME_TYPES = frozenset({"image/gif", "image/jpeg", "image/png", "image/webp"})
    _MIME_BY_SUFFIX = {
        ".gif": "image/gif",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    _DISCORD_MEDIA_HOSTS = frozenset({"cdn.discordapp.com", "media.discordapp.net"})
    # GIF-picker messages are embeds, not attachments. Discord can expose the
    # raster bytes either via Tenor or by copying them into its own CDN. Keep
    # this a small, explicit allow-list rather than accepting arbitrary embed
    # URLs.
    _GIF_PICKER_MEDIA_HOSTS = frozenset({"media.tenor.com", "c.tenor.com"})
    _TRUSTED_EMBED_MEDIA_HOSTS = _DISCORD_MEDIA_HOSTS | _GIF_PICKER_MEDIA_HOSTS
    # Stop at Markdown link delimiters too: Discord retains `[label](URL)` in
    # message.content, and treating both URLs plus `](` as one URL corrupts
    # signed CDN query parameters.
    _HTTPS_URL = re.compile(r"https://[^\s<>\[\]()+]+", re.IGNORECASE)

    @classmethod
    def normalize_many(cls, attachments: Iterable[DiscordAttachment]) -> tuple[MediaAttachmentRequest, ...]:
        return tuple(item for attachment in attachments if (item := cls.normalize(attachment)) is not None)

    @classmethod
    def normalize_message_media(cls, message: object) -> tuple[MediaAttachmentRequest, ...]:
        """Return images from attachments, direct CDN links and GIF-picker embeds.

        Discord represents a pasted CDN GIF as message text and later creates a
        gateway embed for it. It is not an ``Attachment`` despite looking like
        one in the client, therefore both representations must be handled
        without downloading arbitrary third-party URLs from the bot.  GIF-picker
        embeds are separately restricted to Tenor's media CDN and only their
        raster-media URL is accepted; the Tenor page URL itself is ignored.
        """
        media = list(cls.normalize_many(getattr(message, "attachments", ())))
        # Discord's message-content preview and hydrated embed often point to
        # the same attachment through different signed URLs. Query strings are
        # intentionally different, so use the stable Discord attachment path
        # to avoid submitting a stale preview beside the current embed URL.
        known_resources = {
            cls._resource_identity(str(item.download_url))
            for item in media
            if item.download_url is not None
        }
        for index, embed in enumerate(getattr(message, "embeds", ())):
            item = cls._normalize_trusted_embed_media(embed, index)
            if item is not None and cls._resource_identity(str(item.download_url)) not in known_resources:
                media.append(item)
                known_resources.add(cls._resource_identity(str(item.download_url)))
        content = str(getattr(message, "content", "") or "")
        for index, raw_url in enumerate(cls._HTTPS_URL.findall(content)):
            url = raw_url.rstrip(".,!?:;\")]}>")
            item = cls._normalize_discord_cdn_url(url, index)
            if item is not None and cls._resource_identity(str(item.download_url)) not in known_resources:
                media.append(item)
                known_resources.add(cls._resource_identity(str(item.download_url)))
        return tuple(media)

    @classmethod
    def message_text_without_media_urls(
        cls,
        message: object,
        media: Iterable[MediaAttachmentRequest],
    ) -> str:
        """Return user text without links which are being analyzed as media.

        A Discord GIF-picker message can contain a CDN URL as its only text
        content, while the same URL (or the same attachment path with a newer
        signature) is submitted separately as an OCR attachment.  Passing it
        to the text classifier creates a false ``URL``/``EVASION`` finding for
        the transport URL.  Remove only URLs that resolve to one of the
        already-selected media resources; captions and unrelated links remain
        ordinary message text and continue through text moderation.
        """
        media_resources = {
            cls._resource_identity(str(item.download_url))
            for item in media
            if item.download_url is not None
        }
        if not media_resources:
            return str(getattr(message, "content", "") or "")

        def remove_media_url(match: re.Match[str]) -> str:
            raw_url = match.group(0)
            url = raw_url.rstrip(".,!?:;\")]}>" )
            normalized = cls._normalize_discord_cdn_url(url, 0)
            identity = (
                cls._resource_identity(str(normalized.download_url))
                if normalized is not None
                else cls._resource_identity(url)
            )
            return "" if identity in media_resources else raw_url

        text = cls._HTTPS_URL.sub(remove_media_url, str(getattr(message, "content", "") or ""))
        # Discord's ``<URL>`` suppression syntax would otherwise leave an
        # empty ``<>`` token after removing the delivery link.
        return text.replace("<>", "").strip()

    @classmethod
    def normalize(cls, attachment: DiscordAttachment) -> MediaAttachmentRequest | None:
        content_type = cls._image_content_type(attachment.content_type, attachment.filename)
        if content_type is None:
            return None
        return MediaAttachmentRequest(
            attachment_id=str(attachment.id),
            # Discord can surface signed CDN query delimiters as ``&amp;`` in
            # an embed or a copied rich-link value.  Core must receive the
            # canonical URL; ``&amp;`` is otherwise sent literally and Discord
            # CDN responds 404 although the media is still valid.
            download_url=unescape(str(attachment.url)),
            file_name=attachment.filename,
            content_type=content_type,
            file_size=attachment.size,
            width=attachment.width,
            height=attachment.height,
        )

    @classmethod
    def _normalize_discord_cdn_url(cls, url: str, index: int) -> MediaAttachmentRequest | None:
        url = unescape(url)
        parsed = urlparse(url)
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in cls._DISCORD_MEDIA_HOSTS:
            return None
        filename = PurePosixPath(parsed.path).name
        content_type = cls._image_content_type(None, filename)
        if content_type is None:
            return None
        return MediaAttachmentRequest(
            attachment_id=f"url-{index}-{sha256(url.encode('utf-8')).hexdigest()[:16]}",
            download_url=url,
            file_name=filename,
            content_type=content_type,
        )

    @classmethod
    def _resource_identity(cls, url: str) -> str:
        """Return a stable identity for deduplicating trusted Discord CDN URLs."""
        canonical = unescape(url)
        parsed = urlparse(canonical)
        host = (parsed.hostname or "").casefold()
        if host in cls._DISCORD_MEDIA_HOSTS:
            return f"discord:{parsed.path}"
        return canonical

    @classmethod
    def _normalize_trusted_embed_media(cls, embed: object, index: int) -> MediaAttachmentRequest | None:
        """Extract raster media from the trusted fields of a Discord-rich embed.

        GIF picker output is not uniform: some messages have ``video.url`` on
        Tenor, while others are ``type=image`` embeds with the GIF only in
        ``thumbnail.url`` on Discord's CDN.  ``embed.url`` is included as a
        final fallback because Discord uses it as the only media URL for some
        image embeds.  Every candidate remains host- and suffix-restricted.
        """
        candidates = (
            ("video", getattr(embed, "video", None)),
            ("image", getattr(embed, "image", None)),
            ("thumbnail", getattr(embed, "thumbnail", None)),
            ("url", embed),
        )
        for field_name, field in candidates:
            url = unescape(str(getattr(field, "url", "") or ""))
            parsed = urlparse(url)
            if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in cls._TRUSTED_EMBED_MEDIA_HOSTS:
                continue
            filename = PurePosixPath(parsed.path).name
            content_type = cls._image_content_type(None, filename)
            if content_type is None:
                continue
            return MediaAttachmentRequest(
                attachment_id=f"embed-{index}-{sha256(url.encode('utf-8')).hexdigest()[:16]}",
                download_url=url,
                file_name=filename,
                content_type=content_type,
                width=getattr(field, "width", None),
                height=getattr(field, "height", None),
            )
        return None

    @classmethod
    def _image_content_type(cls, raw_content_type: str | None, filename: str) -> str | None:
        declared = (raw_content_type or "").split(";", 1)[0].strip().casefold()
        if declared in cls._IMAGE_MIME_TYPES:
            return declared
        return cls._MIME_BY_SUFFIX.get(PurePosixPath(filename).suffix.casefold())
