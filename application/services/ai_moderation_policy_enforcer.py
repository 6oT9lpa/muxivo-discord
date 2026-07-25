"""Translate an AI recommendation into the action permitted by guild policy.

This is intentionally the only layer that can turn a recommendation from the
AI service into an executable Discord action.  It keeps model inference,
server-specific rules and enforcement safety boundaries separate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlparse

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from core.domain.ai_moderation_action import AiModerationAction
from core.domain.ai_moderation_guild_policy import AiModerationGuildPolicy
from core.domain.ai_moderation_label_policy import AiModerationLabelPolicy
from core.domain.ai_moderation_enforcement_mode import AiModerationEnforcementMode
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class AiModerationPolicyEnforcer:
    """Apply label rules, hard-rule evidence and enforcement-mode guardrails."""
    _ACTION_RANK = {
        AiModerationAction.IGNORE: 0,
        AiModerationAction.LOG: 1,
        AiModerationAction.REVIEW: 2,
        AiModerationAction.WARN: 3,
        AiModerationAction.DELETE: 4,
        AiModerationAction.DELETE_WARN: 5,
        AiModerationAction.TIMEOUT: 6,
        AiModerationAction.KICK: 7,
        AiModerationAction.BAN: 8,
    }

    def apply(
        self,
        request: AiModerationRequest,
        decision: AiModerationDecision,
        raw_policy: Mapping[str, object],
    ) -> AiModerationDecision:
        """Return a decision with a preserved proposal and a safe execution plan.

        The returned ``proposed_action`` is useful for Shadow Mode metrics;
        ``action`` is the only value the Discord cog is allowed to execute.
        """
        policy = AiModerationGuildPolicy.model_validate(raw_policy)
        if self._is_excluded(policy, request):
            return decision.model_copy(
                update={
                    "action": AiModerationAction.IGNORE.value,
                    "proposed_action": decision.action,
                    "execution_plan": (AiModerationAction.IGNORE.value,),
                }
            )
        configured_action = self._configured_action(policy, decision)
        blacklist_action = self._blacklist_action(policy, request.raw_text)
        domain_action = self._unapproved_domain_action(policy, request.raw_text)
        history_action = self._repeat_offender_action(policy, request, decision)
        action = max(
            (candidate for candidate in (configured_action, blacklist_action, domain_action, history_action) if candidate is not None),
            key=lambda candidate: self._ACTION_RANK[candidate],
            default=AiModerationAction(decision.action),
        )
        primary_label = "BLACKLIST" if blacklist_action is not None else decision.primary_label
        labels = decision.labels if blacklist_action is None else tuple(dict.fromkeys((*decision.labels, "BLACKLIST")))
        proposed_action = action
        action = self._limit_enforcement(proposed_action, decision, policy)
        dry_run = decision.dry_run
        if policy.test_mode:
            # Test mode evaluates each live message against the complete
            # server policy, including elevated outcomes such as BAN.  The
            # action stays visible in logs, but ``dry_run`` prevents every
            # Discord mutation and punishment-history write downstream.
            action = proposed_action
            dry_run = True
        execution_plan = self._execution_plan(action)
        if (
            action.value == decision.action
            and primary_label == decision.primary_label
            and execution_plan == decision.execution_plan
            and dry_run == decision.dry_run
        ):
            return decision
        logger.info(
            "Applied guild AI moderation policy guild_id=%s message_id=%s action=%s",
            request.guild_id,
            request.message_id,
            action.value,
        )
        return decision.model_copy(
            update={
                "action": action.value,
                "proposed_action": proposed_action.value,
                "primary_label": primary_label,
                "labels": labels,
                "execution_plan": execution_plan,
                "dry_run": dry_run,
            }
        )

    def _limit_enforcement(
        self,
        proposed_action: AiModerationAction,
        decision: AiModerationDecision,
        policy: AiModerationGuildPolicy,
    ) -> AiModerationAction:
        if proposed_action in {AiModerationAction.IGNORE, AiModerationAction.LOG, AiModerationAction.REVIEW}:
            return proposed_action
        if policy.enforcement_mode == AiModerationEnforcementMode.SHADOW:
            logger.info("Shadow mode suppressed proposed action message_id=%s action=%s", decision.message_id, proposed_action.value)
            return AiModerationAction.REVIEW
        if policy.enforcement_mode == AiModerationEnforcementMode.LIMITED:
            return self._limited_action(proposed_action, decision, policy)
        return self._elevated_action(proposed_action, policy)

    def _limited_action(
        self,
        proposed_action: AiModerationAction,
        decision: AiModerationDecision,
        policy: AiModerationGuildPolicy,
    ) -> AiModerationAction:
        hard_rule_match = bool(set(label.upper() for label in decision.labels) & set(policy.limited_hard_rule_labels)) and bool(decision.rule_matches)
        is_high_confidence = decision.confidence >= policy.limited_min_confidence
        if proposed_action in {AiModerationAction.DELETE, AiModerationAction.DELETE_WARN} and hard_rule_match and is_high_confidence:
            return proposed_action
        if proposed_action in {AiModerationAction.WARN, AiModerationAction.DELETE, AiModerationAction.DELETE_WARN}:
            return AiModerationAction.WARN
        return AiModerationAction.REVIEW

    def _elevated_action(self, proposed_action: AiModerationAction, policy: AiModerationGuildPolicy) -> AiModerationAction:
        if not policy.beta_enforcement_acknowledged:
            return AiModerationAction.REVIEW
        switches = {
            AiModerationAction.TIMEOUT: policy.allow_automated_timeout,
            AiModerationAction.KICK: policy.allow_automated_kick,
            AiModerationAction.BAN: policy.allow_automated_ban,
        }
        if proposed_action in switches and not switches[proposed_action]:
            return AiModerationAction.REVIEW
        return proposed_action

    def validate(self, raw_policy: Mapping[str, object]) -> dict[str, object]:
        return AiModerationGuildPolicy.model_validate(raw_policy).model_dump(mode="json")

    def _configured_action(self, policy: AiModerationGuildPolicy, decision: AiModerationDecision) -> AiModerationAction | None:
        configured_actions = [
            self._apply_label_rule(rule, decision)
            for label in decision.labels
            if (rule := policy.labels.get(label.upper())) is not None
        ]
        return max(configured_actions, key=lambda action: self._ACTION_RANK[action], default=None)

    def _apply_label_rule(self, rule: AiModerationLabelPolicy, decision: AiModerationDecision) -> AiModerationAction:
        if decision.risk_score < rule.risk_threshold:
            return AiModerationAction.LOG
        current_action = AiModerationAction(decision.action)
        if self._ACTION_RANK[current_action] < self._ACTION_RANK[rule.min_action]:
            return rule.min_action
        if self._ACTION_RANK[current_action] > self._ACTION_RANK[rule.max_action]:
            return rule.max_action
        return current_action

    def _blacklist_action(self, policy: AiModerationGuildPolicy, text: str) -> AiModerationAction | None:
        normalized_text = text.casefold()
        for word in policy.blacklist_words:
            if re.search(rf"(?<!\\w){re.escape(word)}(?!\\w)", normalized_text):
                return policy.blacklist_action
        return None

    def _unapproved_domain_action(self, policy: AiModerationGuildPolicy, text: str) -> AiModerationAction | None:
        if not policy.allowed_domains:
            return None
        domains = tuple(
            parsed.hostname.casefold()
            for raw_url in re.findall(r"https?://[^\s<>()]+", text, flags=re.IGNORECASE)
            if (parsed := urlparse(raw_url)).hostname
        )
        if any(not self._is_allowed_domain(domain, policy.allowed_domains) for domain in domains):
            return policy.unapproved_domain_action
        return None

    def _repeat_offender_action(self, policy: AiModerationGuildPolicy, request: AiModerationRequest, decision: AiModerationDecision) -> AiModerationAction | None:
        context = request.user_context
        if (
            not policy.escalation_enabled
            or context is None
            or AiModerationAction(decision.action) in {AiModerationAction.IGNORE, AiModerationAction.LOG}
        ):
            return None
        return (
            policy.repeat_offender_action
            if context.punishments.weighted_escalation_score >= policy.escalation_score_threshold
            else None
        )

    @staticmethod
    def _is_excluded(policy: AiModerationGuildPolicy, request: AiModerationRequest) -> bool:
        return (
            request.user_id in policy.excluded_user_ids
            or request.channel_id in policy.excluded_channel_ids
            or bool(set(request.author_role_ids) & set(policy.excluded_role_ids))
            or (request.author_is_bot and policy.exclude_bots)
        )

    def _is_allowed_domain(self, domain: str, allowed_domains: tuple[str, ...]) -> bool:
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)

    def _execution_plan(self, action: AiModerationAction) -> tuple[str, ...]:
        if action == AiModerationAction.DELETE_WARN:
            return (AiModerationAction.DELETE.value, AiModerationAction.WARN.value)
        if action in {AiModerationAction.TIMEOUT, AiModerationAction.KICK, AiModerationAction.BAN}:
            # A high-impact moderation action must not leave the violating
            # content visible while the member restriction takes effect.
            return (AiModerationAction.DELETE.value, action.value)
        return (action.value,)
