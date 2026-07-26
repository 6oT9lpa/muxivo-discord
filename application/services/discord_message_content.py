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
            embeds=tuple(sorted(self._embeds(getattr(message, "embeds", ())))),
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

    def _embeds(self, embeds: Iterable[object]) -> Iterable[tuple[str, str, str, str]]:
        for embed in embeds:
            # Discord emits an update after it hydrates its automatic preview
            # for a URL already present in the message. That gateway update is
            # not a user edit and must not produce a moderation/audit entry.
            if self._text(getattr(embed, "type", "")) == "link":
                continue
            yield (
                self._text(getattr(embed, "url", "")),
                self._text(getattr(embed, "title", "")),
                self._text(getattr(embed, "description", "")),
                self._text(getattr(embed, "type", "")),
            )

    def _stickers(self, stickers: Iterable[object]) -> Iterable[tuple[str, str]]:
        for sticker in stickers:
            yield (str(getattr(sticker, "id", "")), self._text(getattr(sticker, "name", "")))

    def _text(self, value: object) -> str:
        return str(value or "").strip()
