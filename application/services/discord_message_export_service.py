from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from infrastructure.logging import get_logger

logger = get_logger(__name__)


class DiscordMessageExportService:
    API_BASE = "https://discord.com/api/v10"
    _USER_MENTION = re.compile(r"<@!?\d+>")
    _ROLE_MENTION = re.compile(r"<@&\d+>")
    _CHANNEL_MENTION = re.compile(r"<#\d+>")

    def __init__(
        self,
        *,
        bot_token: str,
        guild_id: str,
        channel_ids: tuple[str, ...],
        recipient_user_id: str,
        output_directory: Path,
        hash_salt: str,
        proxy_url: str | None = None,
        max_messages: int | None = 5_000,
        max_file_bytes: int = 7_500_000,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not bot_token:
            raise ValueError("Discord bot token is required")
        if len(hash_salt) < 32:
            raise ValueError("Hash salt must contain at least 32 characters")
        if max_messages is not None and max_messages < 1:
            raise ValueError("max_messages must be positive")
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        normalized_channel_ids = tuple(dict.fromkeys(channel_id.strip() for channel_id in channel_ids if channel_id.strip()))
        if not normalized_channel_ids:
            raise ValueError("At least one Discord channel is required")

        self._guild_id = guild_id
        self._channel_ids = normalized_channel_ids
        self._recipient_user_id = recipient_user_id
        self._output_directory = output_directory
        self._hash_salt = hash_salt
        self._max_messages = max_messages
        self._max_file_bytes = max_file_bytes
        self._client = httpx.Client(
            base_url=self.API_BASE,
            headers={
                "Authorization": f"Bot {bot_token}",
                "User-Agent": "Muxivo Discord-DatasetExporter/1.0",
            },
            proxy=proxy_url,
            timeout=30.0,
            trust_env=False,
            transport=transport,
        )

    def run(self) -> dict[str, Any]:
        logger.info(
            "Discord dataset export started guild_id=%s channel_count=%s max_messages_per_channel=%s",
            self._guild_id,
            len(self._channel_ids),
            self._max_messages if self._max_messages is not None else "all",
        )
        try:
            self._validate_channels()
            rows, skipped_bot_messages, skipped_empty_messages, channel_counts = self._collect_rows()
            parts = self._write_jsonl_parts(rows)
            dm_channel_id = self._create_dm_channel()
            self._deliver_parts(dm_channel_id, parts, len(rows))
            manifest = self._write_manifest(
                rows=len(rows),
                parts=parts,
                skipped_bot_messages=skipped_bot_messages,
                skipped_empty_messages=skipped_empty_messages,
                channel_counts=channel_counts,
            )
            logger.info(
                "Discord dataset export completed guild_id=%s channel_count=%s rows=%s parts=%s recipient_user_id=%s",
                self._guild_id,
                len(self._channel_ids),
                len(rows),
                len(parts),
                self._recipient_user_id,
            )
            return manifest
        except Exception:
            logger.exception(
                "Discord dataset export failed guild_id=%s channel_count=%s recipient_user_id=%s",
                self._guild_id,
                len(self._channel_ids),
                self._recipient_user_id,
            )
            raise
        finally:
            self._client.close()

    def _validate_channels(self) -> None:
        for channel_id in self._channel_ids:
            channel = self._request("GET", f"/channels/{channel_id}").json()
            if str(channel.get("guild_id")) != self._guild_id:
                raise ValueError(f"Configured channel does not belong to the configured guild channel_id={channel_id}")
            logger.info("Discord export channel validated guild_id=%s channel_id=%s", self._guild_id, channel_id)

    def _collect_rows(self) -> tuple[list[dict[str, Any]], int, int, dict[str, dict[str, int]]]:
        rows: list[dict[str, Any]] = []
        total_skipped_bot_messages = 0
        total_skipped_empty_messages = 0
        channel_counts: dict[str, dict[str, int]] = {}

        for channel_id in self._channel_ids:
            channel_rows, skipped_bot_messages, skipped_empty_messages = self._collect_channel_rows(channel_id)
            rows.extend(channel_rows)
            total_skipped_bot_messages += skipped_bot_messages
            total_skipped_empty_messages += skipped_empty_messages
            channel_counts[channel_id] = {
                "rows": len(channel_rows),
                "skipped_bot_messages": skipped_bot_messages,
                "skipped_empty_messages": skipped_empty_messages,
            }

        return rows, total_skipped_bot_messages, total_skipped_empty_messages, channel_counts

    def _collect_channel_rows(self, channel_id: str) -> tuple[list[dict[str, Any]], int, int]:
        rows: list[dict[str, Any]] = []
        skipped_bot_messages = 0
        skipped_empty_messages = 0
        before: str | None = None

        while self._max_messages is None or len(rows) + skipped_bot_messages + skipped_empty_messages < self._max_messages:
            exported_count = len(rows) + skipped_bot_messages + skipped_empty_messages
            remaining = 100 if self._max_messages is None else self._max_messages - exported_count
            params: dict[str, str | int] = {"limit": min(100, remaining)}
            if before:
                params["before"] = before
            messages = self._request("GET", f"/channels/{channel_id}/messages", params=params).json()
            if not messages:
                break

            for message in messages:
                before = str(message["id"])
                author = message.get("author") if isinstance(message.get("author"), dict) else {}
                if author.get("bot"):
                    skipped_bot_messages += 1
                    continue
                row = self._to_training_row(message, channel_id)
                if row is None:
                    skipped_empty_messages += 1
                    continue
                rows.append(row)

            if len(messages) < 100:
                break

        logger.info(
            "Discord messages collected channel_id=%s rows=%s skipped_bots=%s skipped_empty=%s",
            channel_id,
            len(rows),
            skipped_bot_messages,
            skipped_empty_messages,
        )
        return rows, skipped_bot_messages, skipped_empty_messages

    def _to_training_row(self, message: dict[str, Any], channel_id: str) -> dict[str, Any] | None:
        content = self._sanitize_content(str(message.get("content") or ""))
        if not content:
            return None
        author = message.get("author") if isinstance(message.get("author"), dict) else {}
        return {
            "message_id": str(message.get("id", "")),
            "model_text": content,
            "labels": ["SAFE"],
            "primary_label": "SAFE",
            "severity": 0,
            "source": "real_safe",
            "feedback_type": "confirmed",
            "annotation_source": "discord_export",
            "created_at": message.get("timestamp"),
            "metadata": {
                "source_bucket": "project",
                "source_tag": "discord_safe_training_channel",
                "guild_id_hash": self._hash(self._guild_id),
                "channel_id_hash": self._hash(channel_id),
                "user_id_hash": self._hash(str(author.get("id", ""))),
                "attachments_count": len(message.get("attachments") or []),
                "embeds_count": len(message.get("embeds") or []),
            },
        }

    def _sanitize_content(self, content: str) -> str:
        content = self._USER_MENTION.sub("@user", content)
        content = self._ROLE_MENTION.sub("@role", content)
        content = self._CHANNEL_MENTION.sub("#channel", content)
        return " ".join(content.replace("\x00", " ").split())

    def _write_jsonl_parts(self, rows: list[dict[str, Any]]) -> list[Path]:
        self._output_directory.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        current_file = None
        current_size = 0

        try:
            for row in rows:
                encoded = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
                if len(encoded) > self._max_file_bytes:
                    raise ValueError("A single JSONL row exceeds the Discord upload limit")
                if current_file is None or current_size + len(encoded) > self._max_file_bytes:
                    if current_file is not None:
                        current_file.close()
                    part_path = self._output_directory / f"discord_messages_part_{len(parts) + 1:03d}.jsonl"
                    parts.append(part_path)
                    current_file = part_path.open("wb")
                    current_size = 0
                current_file.write(encoded)
                current_size += len(encoded)
        finally:
            if current_file is not None:
                current_file.close()

        if not parts:
            part_path = self._output_directory / "discord_messages_part_001.jsonl"
            part_path.write_bytes(b"")
            parts.append(part_path)
        logger.info("Discord JSONL files written parts=%s rows=%s", len(parts), len(rows))
        return parts

    def _create_dm_channel(self) -> str:
        response = self._request("POST", "/users/@me/channels", json={"recipient_id": self._recipient_user_id})
        channel_id = str(response.json()["id"])
        logger.info("Discord export DM channel resolved recipient_user_id=%s", self._recipient_user_id)
        return channel_id

    def _deliver_parts(self, dm_channel_id: str, parts: list[Path], row_count: int) -> None:
        for index, part in enumerate(parts, start=1):
            payload = {
                "content": f"Экспорт сообщений: часть {index}/{len(parts)}. Строк в полной выгрузке: {row_count}.",
                "allowed_mentions": {"parse": []},
            }
            with part.open("rb") as attachment:
                self._request(
                    "POST",
                    f"/channels/{dm_channel_id}/messages",
                    data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                    files={"files[0]": (part.name, attachment, "application/x-ndjson")},
                )
            logger.info(
                "Discord export part delivered recipient_user_id=%s part=%s size_bytes=%s",
                self._recipient_user_id,
                index,
                part.stat().st_size,
            )

    def _write_manifest(
        self,
        *,
        rows: int,
        parts: list[Path],
        skipped_bot_messages: int,
        skipped_empty_messages: int,
        channel_counts: dict[str, dict[str, int]],
    ) -> dict[str, Any]:
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "guild_id_hash": self._hash(self._guild_id),
            "channel_id_hashes": {channel_id: self._hash(channel_id) for channel_id in self._channel_ids},
            "channel_counts": channel_counts,
            "rows": rows,
            "parts": [part.name for part in parts],
            "part_sizes": [part.stat().st_size for part in parts],
            "skipped_bot_messages": skipped_bot_messages,
            "skipped_empty_messages": skipped_empty_messages,
        }
        path = self._output_directory / "discord_export_manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Discord export manifest written path=%s", path)
        return manifest

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(1, 6):
            response = self._client.request(method, path, **kwargs)
            if response.status_code == 429:
                retry_after = float(response.json().get("retry_after", 1.0))
                logger.warning("Discord export rate limited path=%s retry_after=%s", path, retry_after)
                time.sleep(retry_after + 0.25)
                continue
            if response.status_code >= 500 and attempt < 5:
                logger.warning("Discord export request retry path=%s status=%s attempt=%s", path, response.status_code, attempt)
                time.sleep(min(2**attempt, 10))
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"Discord API request failed after retries path={path}")

    def _hash(self, value: str) -> str:
        return hashlib.sha256(f"{self._hash_salt}:{value}".encode("utf-8")).hexdigest()
