from activity.server.services.ai_moderation_service import AiModerationService
from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy


def test_activity_service_uses_default_policy_when_stored_policy_is_invalid() -> None:
    service = AiModerationService()

    policy, is_default = service._effective_policy({"labels": "invalid"}, 1)

    assert is_default is True
    assert policy["labels"]["TOXIC"]["risk_threshold"] == 45


def test_activity_service_keeps_valid_stored_policy() -> None:
    service = AiModerationService()
    stored_policy = {
        "blacklist_words": [],
        "allowed_domains": [],
        "labels": {},
        "blacklist_action": "DELETE_WARN",
        "unapproved_domain_action": "REVIEW",
    }

    policy, is_default = service._effective_policy(stored_policy, 1)

    assert is_default is False
    assert policy["blacklist_action"] == stored_policy["blacklist_action"]
    assert policy["labels"]["PROFANITY"]["max_action"] == "WARN"
    assert policy["labels"]["POLITICS_IRL"]["min_action"] == "REVIEW"


def test_activity_service_uses_defaults_for_legacy_zero_model_sensitivity() -> None:
    service = AiModerationService()
    policy, is_default = service._effective_policy(
        {"labels": {"SCAM": {"model_min_risk": 0}}},
        1,
    )

    assert is_default is False
    assert policy["labels"]["SCAM"]["model_min_risk"] == 60
    assert policy["labels"]["TOXIC"]["model_min_risk"] == 50


def test_activity_service_keeps_explicit_model_sensitivity_zero() -> None:
    service = AiModerationService()
    policy, _ = service._effective_policy(
        {
            "labels": {"SCAM": {"model_min_risk": 0}},
            "model_min_risk_overrides": {"SCAM": 0},
        },
        1,
    )

    assert policy["labels"]["SCAM"]["model_min_risk"] == 0


def test_activity_service_persists_only_changed_model_sensitivity_values() -> None:
    service = AiModerationService()
    policy = AiModerationGuildPolicy.model_validate({
        "labels": {
            "TOXIC": {"model_min_risk": 50},
            "SCAM": {"model_min_risk": 0},
        },
    })

    stored = service._with_model_sensitivity_overrides(policy)

    assert stored.model_min_risk_overrides == {"SCAM": 0}
