from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Protocol

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

    @classmethod
    def normalize_many(cls, attachments: Iterable[DiscordAttachment]) -> tuple[MediaAttachmentRequest, ...]:
        return tuple(item for attachment in attachments if (item := cls.normalize(attachment)) is not None)

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
    def _image_content_type(cls, raw_content_type: str | None, filename: str) -> str | None:
        declared = (raw_content_type or "").split(";", 1)[0].strip().casefold()
        if declared in cls._IMAGE_MIME_TYPES:
            return declared
        return cls._MIME_BY_SUFFIX.get(PurePosixPath(filename).suffix.casefold())
