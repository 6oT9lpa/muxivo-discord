from datetime import datetime, timezone

from application.dto.ai_moderation_request import AiModerationRequest
from application.dto.user_moderation_context import UserModerationContext, UserPunishmentStatistics
from infrastructure.ai.ai_moderator_api_client import AiModeratorApiClient


def test_ai_moderator_payload_serializes_discord_ids_as_strings() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1150681470634049668,
            channel_id=1525175773722579145,
            user_id=762514681209946122,
            message_id=1525175773722579145,
            reply_to_message_id=1525175773722579144,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
            mention_count=2,
        )
    )

    assert payload["platform"] == "discord"
    assert payload["guild_id"] == "1150681470634049668"
    assert payload["channel_id"] == "1525175773722579145"
    assert payload["user_id"] == "762514681209946122"
    assert payload["message_id"] == "1525175773722579145"
    assert payload["reply_to_message_id"] == "1525175773722579144"
    assert payload["mention_count"] == 2


def test_ai_moderator_payload_includes_validated_user_context() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1,
            channel_id=2,
            user_id=3,
            message_id=4,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
            event_type="UPDATE",
            user_context=UserModerationContext(
                account_age_days=100,
                guild_membership_days=10,
                punishments=UserPunishmentStatistics(window_days=30, total_in_window=2),
            ),
        )
    )
    assert payload["event_type"] == "UPDATE"
    assert payload["user_context"]["punishments"]["total_in_window"] == 2


def test_ai_moderator_payload_does_not_include_removed_author_fields() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1,
            channel_id=2,
            user_id=3,
            message_id=4,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert "author_role_ids" not in payload
    assert "author_is_bot" not in payload
