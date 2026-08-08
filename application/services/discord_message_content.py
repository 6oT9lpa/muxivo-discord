from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedDiscordMessageContent:
    text: str
    attachments: tuple[tuple[str, str, str], ...]
    embeds: tuple[tuple[str, str, str, str], ...]
    stickers: tuple[tuple[str, str], ...]


class DiscordMessageContentNormalizer:
    """Compares only user-visible moderation content, not Discord cache metadata."""

    def normalize(self, message: object) -> NormalizedDiscordMessageContent:
        return NormalizedDiscordMessageContent(
            text=self._text(getattr(message, "content", "")),
            attachments=tuple(sorted(self._attachments(getattr(message, "attachments", ())))),
            # User messages cannot contain native embeds. Discord hydrates all
            # embeds (including GIF/image previews) after message creation.
            embeds=(),
            stickers=tuple(sorted(self._stickers(getattr(message, "stickers", ())))),
        )

    def changed(self, before: object, after: object) -> bool:
        return self.normalize(before) != self.normalize(after)

    def _attachments(self, attachments: Iterable[object]) -> Iterable[tuple[str, str, str]]:
        for attachment in attachments:
            yield (
                self._text(getattr(attachment, "url", "")),
                self._text(getattr(attachment, "filename", "")),
                self._text(getattr(attachment, "content_type", "")),
            )

    def _stickers(self, stickers: Iterable[object]) -> Iterable[tuple[str, str]]:
        for sticker in stickers:
            yield (str(getattr(sticker, "id", "")), self._text(getattr(sticker, "name", "")))

    def _text(self, value: object) -> str:
        return str(value or "").strip()
