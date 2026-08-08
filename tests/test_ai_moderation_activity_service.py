from activity.server.services.ai_moderation_service import AiModerationService


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
