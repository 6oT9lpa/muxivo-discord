import pytest

from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy
from core.domain.default_ai_moderation_policy import default_ai_moderation_policy, merge_with_default_ai_moderation_policy


def test_default_ai_moderation_policy_covers_moderated_labels() -> None:
    policy = default_ai_moderation_policy()

    assert policy.labels["TOXIC"].risk_threshold == 45
    assert policy.labels["PROFANITY"].max_action == "WARN"
    assert policy.labels["POLITICS_IRL"].min_action == "REVIEW"
    assert policy.labels["POLITICS_IRL"].max_action == "REVIEW"
    assert policy.labels["SCAM"].min_action == "DELETE_WARN"
    assert policy.labels["THREAT"].max_action == "TIMEOUT"
    assert policy.labels["FLOOD"].min_action == "TIMEOUT"
    assert policy.enforcement_mode == "SHADOW"
    assert policy.ocr_enabled is False
    assert policy.model_min_risk == 0
    assert policy.blacklist_words == ()
    assert policy.allowed_domains == ()


def test_default_policy_is_merged_into_existing_guild_policy() -> None:
    policy = merge_with_default_ai_moderation_policy(
        AiModerationGuildPolicy.model_validate({"labels": {"TOXIC": {"risk_threshold": 60, "min_action": "WARN", "max_action": "WARN"}}})
    )

    assert policy.labels["TOXIC"].risk_threshold == 60
    assert policy.labels["PROFANITY"].max_action == "WARN"
    assert policy.labels["POLITICS_IRL"].min_action == "REVIEW"
    assert policy.ocr_enabled is False


def test_ocr_setting_is_preserved_for_a_guild_policy() -> None:
    policy = merge_with_default_ai_moderation_policy(AiModerationGuildPolicy.model_validate({"ocr_enabled": True}))

    assert policy.ocr_enabled is True


def test_model_sensitivity_is_validated_and_preserved_for_a_guild_policy() -> None:
    policy = merge_with_default_ai_moderation_policy(
        AiModerationGuildPolicy.model_validate({"model_min_risk": 80})
    )

    assert policy.model_min_risk == 80
    with pytest.raises(ValueError):
        AiModerationGuildPolicy.model_validate({"model_min_risk": 101})


def test_legacy_default_threat_rule_is_upgraded_to_timeout() -> None:
    policy = merge_with_default_ai_moderation_policy(
        AiModerationGuildPolicy.model_validate({
            "labels": {"THREAT": {"risk_threshold": 65, "min_action": "DELETE_WARN", "max_action": "DELETE_WARN"}},
        })
    )

    assert policy.labels["THREAT"].min_action == "TIMEOUT"
    assert policy.labels["THREAT"].max_action == "TIMEOUT"


def test_legacy_default_flood_rule_is_upgraded_to_timeout() -> None:
    policy = merge_with_default_ai_moderation_policy(
        AiModerationGuildPolicy.model_validate({
            "labels": {"FLOOD": {"risk_threshold": 30, "min_action": "LOG", "max_action": "DELETE"}},
        })
    )

    assert policy.labels["FLOOD"].risk_threshold == 20
    assert policy.labels["FLOOD"].min_action == "TIMEOUT"


def test_high_action_recommendations_are_safe_outside_elevated_mode() -> None:
    shadow_policy = AiModerationGuildPolicy.model_validate({"labels": {"TOXIC": {"max_action": "TIMEOUT"}}})
    assert shadow_policy.labels["TOXIC"].max_action == "TIMEOUT"

    with pytest.raises(ValueError, match="beta acknowledgement"):
        AiModerationGuildPolicy.model_validate({
            "enforcement_mode": "ELEVATED",
            "allow_automated_timeout": True,
        })

    policy = AiModerationGuildPolicy.model_validate({
        "enforcement_mode": "ELEVATED",
        "beta_enforcement_acknowledged": True,
        "allow_automated_timeout": True,
        "labels": {"TOXIC": {"max_action": "TIMEOUT"}},
    })
    assert policy.labels["TOXIC"].max_action == "TIMEOUT"
import pytest
