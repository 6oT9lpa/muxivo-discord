from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit


_MAX_ATTACHMENTS_TO_LIST = 5
_MAX_ATTACHMENT_FILE_NAME_LENGTH = 96
_MAX_ATTACHMENT_FIELD_LENGTH = 1_024
_IMAGE_CONTENT_TYPE_PREFIX = "image/"
_IMAGE_SUFFIXES = frozenset({".gif", ".jpeg", ".jpg", ".png", ".webp"})
_BYTE_UNITS = ("B", "KiB", "MiB", "GiB")
_BYTES_PER_UNIT = 1_024
_MARKDOWN_LINK_LABEL_ESCAPE_CHARACTERS = ("\\", "[", "]", "(", ")")


class DiscordAttachment(Protocol):
    filename: str
    url: str
    content_type: str | None
    size: int


@dataclass(frozen=True)
class DeletedMessageAttachmentPresentation:
    field_value: str | None
    preview_url: str | None


class DeletedMessageAttachmentPresenter:
    """Builds bounded, moderator-readable attachment information for delete logs."""

    @classmethod
    def present(cls, attachments: Iterable[DiscordAttachment]) -> DeletedMessageAttachmentPresentation:
        items = tuple(attachments)
        if not items:
            return DeletedMessageAttachmentPresentation(field_value=None, preview_url=None)

        visible_items = items[:_MAX_ATTACHMENTS_TO_LIST]
        lines = [cls._line(item) for item in visible_items]
        if len(items) > len(visible_items):
            lines.append(f"… and {len(items) - len(visible_items)} more attachment(s)")
        return DeletedMessageAttachmentPresentation(
            field_value="\n".join(lines)[:_MAX_ATTACHMENT_FIELD_LENGTH],
            preview_url=next(
                (str(item.url) for item in visible_items if cls._is_image(item)),
                None,
            ),
        )

    @classmethod
    def _line(cls, attachment: DiscordAttachment) -> str:
        file_name = cls._truncate(cls._escape_link_label(str(attachment.filename)))
        metadata = cls._metadata(attachment)
        url = str(attachment.url)
        if cls._is_https_url(url):
            return f"• [{file_name}]({url}) — {metadata}"
        return f"• {file_name} — {metadata}"

    @staticmethod
    def _metadata(attachment: DiscordAttachment) -> str:
        content_type = (attachment.content_type or "unknown type").split(";", 1)[0].strip()
        return f"{content_type}, {DeletedMessageAttachmentPresenter._format_size(attachment.size)}"

    @staticmethod
    def _truncate(value: str) -> str:
        return value[:_MAX_ATTACHMENT_FILE_NAME_LENGTH] + ("…" if len(value) > _MAX_ATTACHMENT_FILE_NAME_LENGTH else "")

    @staticmethod
    def _escape_link_label(value: str) -> str:
        for character in _MARKDOWN_LINK_LABEL_ESCAPE_CHARACTERS:
            value = value.replace(character, f"\\{character}")
        return value

    @staticmethod
    def _format_size(size: int) -> str:
        value = max(0, int(size))
        for unit in _BYTE_UNITS[:-1]:
            if value < _BYTES_PER_UNIT:
                return f"{value} {unit}"
            value /= _BYTES_PER_UNIT
        return f"{value:.1f} {_BYTE_UNITS[-1]}"

    @staticmethod
    def _is_https_url(value: str) -> bool:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname)

    @classmethod
    def _is_image(cls, attachment: DiscordAttachment) -> bool:
        content_type = (attachment.content_type or "").split(";", 1)[0].strip().casefold()
        return content_type.startswith(_IMAGE_CONTENT_TYPE_PREFIX) or any(
            str(attachment.filename).casefold().endswith(suffix)
            for suffix in _IMAGE_SUFFIXES
        )
