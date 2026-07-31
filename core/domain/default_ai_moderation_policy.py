from core.domain.ai_moderation_action import AiModerationAction
from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy
from core.domain.ai_moderation_label_policy import AiModerationLabelPolicy


def default_ai_moderation_policy() -> AiModerationGuildPolicy:
    return AiModerationGuildPolicy(
        labels={
            "SPAM": AiModerationLabelPolicy(risk_threshold=30, max_action=AiModerationAction.DELETE),
            "ADVERTISEMENT": AiModerationLabelPolicy(risk_threshold=25, max_action=AiModerationAction.DELETE),
            "INVITE": AiModerationLabelPolicy(risk_threshold=20, max_action=AiModerationAction.DELETE),
            "SCAM": AiModerationLabelPolicy(
                risk_threshold=55,
                min_action=AiModerationAction.DELETE_WARN,
                max_action=AiModerationAction.DELETE_WARN,
            ),
            "TOXIC": AiModerationLabelPolicy(risk_threshold=45, max_action=AiModerationAction.WARN),
            "PROFANITY": AiModerationLabelPolicy(risk_threshold=25, max_action=AiModerationAction.WARN),
            "POLITICS_IRL": AiModerationLabelPolicy(
                risk_threshold=40,
                min_action=AiModerationAction.REVIEW,
                max_action=AiModerationAction.REVIEW,
            ),
            "HATE": AiModerationLabelPolicy(
                risk_threshold=55,
                min_action=AiModerationAction.WARN,
                max_action=AiModerationAction.WARN,
            ),
            "THREAT": AiModerationLabelPolicy(
                risk_threshold=65,
                # Elevated enforcement may execute this only when the server
                # explicitly enables automatic timeouts. Other modes still
                # cap it in the policy enforcer before Discord is called.
                min_action=AiModerationAction.TIMEOUT,
                max_action=AiModerationAction.TIMEOUT,
            ),
            "NSFW": AiModerationLabelPolicy(
                risk_threshold=55,
                min_action=AiModerationAction.DELETE,
                max_action=AiModerationAction.DELETE,
            ),
            "EVASION": AiModerationLabelPolicy(
                risk_threshold=50,
                min_action=AiModerationAction.WARN,
                max_action=AiModerationAction.WARN,
            ),
            "FLOOD": AiModerationLabelPolicy(
                risk_threshold=20,
                # The classifier emits FLOOD only from repeated-message
                # context. In Elevated mode this deletes the source message
                # and applies a timeout; lower modes cap it safely.
                min_action=AiModerationAction.TIMEOUT,
                max_action=AiModerationAction.TIMEOUT,
            ),
            "URL": AiModerationLabelPolicy(
                risk_threshold=45,
                min_action=AiModerationAction.REVIEW,
                max_action=AiModerationAction.DELETE,
            ),
        }
    )


def merge_with_default_ai_moderation_policy(policy: AiModerationGuildPolicy) -> AiModerationGuildPolicy:
    """Preserve a guild policy while supplying defaults for labels introduced later."""
    defaults = default_ai_moderation_policy()
    labels = {**defaults.labels, **policy.labels}
    legacy_threat = policy.labels.get("THREAT")
    if (
        legacy_threat is not None
        and legacy_threat.risk_threshold == 65
        and legacy_threat.min_action == AiModerationAction.DELETE_WARN
        and legacy_threat.max_action == AiModerationAction.DELETE_WARN
    ):
        # Upgrade the exact pre-timeout default while preserving any custom
        # THREAT rule an administrator has configured differently.
        labels["THREAT"] = defaults.labels["THREAT"]

    legacy_flood = policy.labels.get("FLOOD")
    if (
        legacy_flood is not None
        and legacy_flood.risk_threshold == 30
        and legacy_flood.min_action == AiModerationAction.LOG
        and legacy_flood.max_action == AiModerationAction.DELETE
    ):
        # Upgrade the exact previous default without overriding a server's
        # deliberately customised flood policy.
        labels["FLOOD"] = defaults.labels["FLOOD"]

    return AiModerationGuildPolicy(
        blacklist_words=policy.blacklist_words,
        allowed_domains=policy.allowed_domains,
        labels=labels,
        blacklist_action=policy.blacklist_action,
        unapproved_domain_action=policy.unapproved_domain_action,
        context_window_days=policy.context_window_days,
        repeat_offender_threshold=policy.repeat_offender_threshold,
        repeat_offender_action=policy.repeat_offender_action,
        escalation_enabled=policy.escalation_enabled,
        escalation_score_threshold=policy.escalation_score_threshold,
        escalation_half_life_days=policy.escalation_half_life_days,
        excluded_user_ids=policy.excluded_user_ids,
        excluded_role_ids=policy.excluded_role_ids,
        excluded_channel_ids=policy.excluded_channel_ids,
        exclude_bots=policy.exclude_bots,
        test_mode=policy.test_mode,
        enforcement_mode=policy.enforcement_mode,
        limited_min_confidence=policy.limited_min_confidence,
        limited_hard_rule_labels=policy.limited_hard_rule_labels,
        beta_enforcement_acknowledged=policy.beta_enforcement_acknowledged,
        allow_automated_timeout=policy.allow_automated_timeout,
        allow_automated_kick=policy.allow_automated_kick,
        allow_automated_ban=policy.allow_automated_ban,
    )
