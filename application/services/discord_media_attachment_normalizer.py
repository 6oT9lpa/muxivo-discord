from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
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
    _HTTPS_URL = re.compile(r"https://[^\s<>]+", re.IGNORECASE)

    @classmethod
    def normalize_many(cls, attachments: Iterable[DiscordAttachment]) -> tuple[MediaAttachmentRequest, ...]:
        return tuple(item for attachment in attachments if (item := cls.normalize(attachment)) is not None)

    @classmethod
    def normalize_message_media(cls, message: object) -> tuple[MediaAttachmentRequest, ...]:
        """Return image attachments plus direct, trusted Discord CDN image links.

        Discord represents a pasted CDN GIF as message text and later creates a
        gateway embed for it. It is not an ``Attachment`` despite looking like
        one in the client, therefore both representations must be handled
        without downloading arbitrary third-party URLs from the bot.
        """
        media = list(cls.normalize_many(getattr(message, "attachments", ())))
        known_urls = {str(item.download_url) for item in media if item.download_url is not None}
        content = str(getattr(message, "content", "") or "")
        for index, raw_url in enumerate(cls._HTTPS_URL.findall(content)):
            url = raw_url.rstrip(".,!?:;\")]}>")
            item = cls._normalize_discord_cdn_url(url, index)
            if item is not None and str(item.download_url) not in known_urls:
                media.append(item)
                known_urls.add(str(item.download_url))
        return tuple(media)

    @classmethod
    def normalize(cls, attachment: DiscordAttachment) -> MediaAttachmentRequest | None:
        content_type = cls._image_content_type(attachment.content_type, attachment.filename)
        if content_type is None:
            return None
        return MediaAttachmentRequest(
            attachment_id=str(attachment.id),
            download_url=str(attachment.url),
            file_name=attachment.filename,
            content_type=content_type,
            file_size=attachment.size,
            width=attachment.width,
            height=attachment.height,
        )

    @classmethod
    def _normalize_discord_cdn_url(cls, url: str, index: int) -> MediaAttachmentRequest | None:
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
    def _image_content_type(cls, raw_content_type: str | None, filename: str) -> str | None:
        declared = (raw_content_type or "").split(";", 1)[0].strip().casefold()
        if declared in cls._IMAGE_MIME_TYPES:
            return declared
        return cls._MIME_BY_SUFFIX.get(PurePosixPath(filename).suffix.casefold())
