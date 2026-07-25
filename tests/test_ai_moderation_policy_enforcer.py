from datetime import datetime, timezone

import pytest

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from application.dto.user_moderation_context import UserModerationContext, UserPunishmentStatistics
from application.services.ai_moderation_policy_enforcer import AiModerationPolicyEnforcer
from core.domain.ai_moderation_action import AiModerationAction
from core.domain.ai_moderation_enforcement_mode import AiModerationEnforcementMode
from core.domain.default_ai_moderation_policy import default_ai_moderation_policy


def test_policy_enforcer_clamps_label_action_and_respects_risk_threshold() -> None:
    enforcer = AiModerationPolicyEnforcer()
    request = _request("ordinary message")
    decision = _decision(action="BAN", risk_score=40, labels=("TOXIC",))

    adjusted = enforcer.apply(
        request,
        decision,
        {"labels": {"TOXIC": {"risk_threshold": 45, "min_action": "LOG", "max_action": "WARN"}}},
    )

    assert adjusted.action == "LOG"
    assert adjusted.execution_plan == ("LOG",)


def test_policy_enforcer_blacklist_overrides_safe_ai_decision() -> None:
    enforcer = AiModerationPolicyEnforcer()
    adjusted = enforcer.apply(
        _request("contains forbidden-term here"),
        _decision(action="IGNORE", risk_score=0, labels=("SAFE",)),
        {"enforcement_mode": "ELEVATED", "beta_enforcement_acknowledged": True, "blacklist_words": ["forbidden-term"]},
    )

    assert adjusted.action == "DELETE_WARN"
    assert adjusted.execution_plan == ("DELETE", "WARN")
    assert adjusted.primary_label == "BLACKLIST"


def test_policy_enforcer_reviews_unapproved_domain() -> None:
    enforcer = AiModerationPolicyEnforcer()
    adjusted = enforcer.apply(
        _request("visit https://untrusted.example/path"),
        _decision(action="IGNORE", risk_score=0, labels=("SAFE",)),
        {"allowed_domains": ["discord.com"]},
    )

    assert adjusted.action == "REVIEW"


def test_policy_enforcer_rejects_inverted_action_range() -> None:
    enforcer = AiModerationPolicyEnforcer()

    with pytest.raises(ValueError, match="min_action"):
        enforcer.validate({"labels": {"TOXIC": {"min_action": "BAN", "max_action": "LOG"}}})


def test_policy_enforcer_does_not_escalate_single_classifier_decision_from_history() -> None:
    enforcer = AiModerationPolicyEnforcer()
    request = _request("ordinary message").model_copy(
        update={
            "user_context": UserModerationContext(
                punishments=UserPunishmentStatistics(window_days=30, total_in_window=3)
            )
        }
    )

    adjusted = enforcer.apply(
        request,
        _decision(action="WARN", risk_score=1, labels=("SAFE",)),
        {"repeat_offender_threshold": 3, "repeat_offender_action": "TIMEOUT"},
    )

    assert adjusted.action == "REVIEW"


def test_shadow_mode_suppresses_proposed_delete() -> None:
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("message"),
        _decision(action="DELETE", risk_score=90, labels=("INVITE",)),
        {},
    )
    assert adjusted.action == "REVIEW"


def test_limited_mode_deletes_only_high_confidence_hard_rule() -> None:
    decision = _decision(action="DELETE", risk_score=90, labels=("INVITE",)).model_copy(
        update={"confidence": 0.99, "rule_matches": ("discord_invite",)}
    )
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("discord.gg/example"), decision, {"enforcement_mode": "LIMITED"}
    )
    assert adjusted.action == "DELETE"


def test_limited_mode_warns_when_hard_rule_evidence_or_confidence_is_missing() -> None:
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("message"),
        _decision(action="DELETE", risk_score=90, labels=("INVITE",)),
        {"enforcement_mode": "LIMITED"},
    )
    assert adjusted.action == "WARN"


@pytest.mark.parametrize("action", ("TIMEOUT", "KICK", "BAN"))
def test_high_impact_actions_delete_the_source_message_first(action: str) -> None:
    enforcer = AiModerationPolicyEnforcer()

    assert enforcer._execution_plan(AiModerationAction(action)) == ("DELETE", action)


def test_elevated_flood_rule_deletes_message_and_times_out_member() -> None:
    policy = default_ai_moderation_policy().model_copy(
        update={"enforcement_mode": AiModerationEnforcementMode.ELEVATED, "beta_enforcement_acknowledged": True, "allow_automated_timeout": True}
    )
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("same message repeated"),
        _decision(action="LOG", risk_score=21, labels=("FLOOD",)),
        policy.model_dump(mode="json"),
    )

    assert adjusted.action == "TIMEOUT"
    assert adjusted.execution_plan == ("DELETE", "TIMEOUT")


def test_policy_exclusion_skips_a_whitelisted_role() -> None:
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("message").model_copy(update={"author_role_ids": (42,)}),
        _decision(action="DELETE", risk_score=90, labels=("SCAM",)),
        {"excluded_role_ids": [42]},
    )

    assert adjusted.action == "IGNORE"
    assert adjusted.execution_plan == ("IGNORE",)


def test_test_mode_preserves_full_decision_but_marks_it_dry_run() -> None:
    adjusted = AiModerationPolicyEnforcer().apply(
        _request("message"),
        _decision(action="DELETE", risk_score=90, labels=("SCAM",)),
        {"enforcement_mode": "ELEVATED", "beta_enforcement_acknowledged": True, "test_mode": True},
    )

    assert adjusted.action == "DELETE"
    assert adjusted.proposed_action == "DELETE"
    assert adjusted.execution_plan == ("DELETE",)
    assert adjusted.dry_run is True


def test_weighted_recent_history_escalates_when_enabled() -> None:
    request = _request("message").model_copy(
        update={
            "user_context": UserModerationContext(
                punishments=UserPunishmentStatistics(window_days=30, weighted_escalation_score=3.0)
            )
        }
    )
    adjusted = AiModerationPolicyEnforcer().apply(
        request,
        _decision(action="WARN", risk_score=90, labels=("TOXIC",)),
        {"enforcement_mode": "ELEVATED", "beta_enforcement_acknowledged": True, "allow_automated_timeout": True},
    )

    assert adjusted.action == "TIMEOUT"


def _request(raw_text: str) -> AiModerationRequest:
    return AiModerationRequest(
        guild_id=1,
        channel_id=2,
        user_id=3,
        message_id=4,
        raw_text=raw_text,
        created_at=datetime.now(timezone.utc),
    )


def _decision(action: str, risk_score: float, labels: tuple[str, ...]) -> AiModerationDecision:
    return AiModerationDecision(
        event_id=1,
        user_id=3,
        guild_id=1,
        message_id=4,
        risk_score=risk_score,
        action=action,
        primary_label=labels[0],
        labels=labels,
        execution_plan=(action,),
        dry_run=False,
    )
