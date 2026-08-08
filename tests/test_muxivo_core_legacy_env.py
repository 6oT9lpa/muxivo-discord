from infrastructure.config import BotConfig


def test_legacy_ai_moderator_environment_variables_configure_muxivo_core(monkeypatch):
    monkeypatch.setenv("AI_MODERATOR_API_URL", "http://legacy-moderator:8000")
    monkeypatch.setenv("AI_MODERATOR_INTERNAL_API_KEY", "legacy-secret")

    config = BotConfig(
        discord_token="test-token",
        database_url="postgresql://test:test@localhost:5432/test",
        _env_file=None,
    )

    assert config.muxivo_core_api_url == "http://legacy-moderator:8000"
    assert config.muxivo_core_internal_api_key is not None
    assert config.muxivo_core_internal_api_key.get_secret_value() == "legacy-secret"
