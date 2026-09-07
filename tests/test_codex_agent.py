from __future__ import annotations

from pathlib import Path

import pytest
from nhs_rag.agent.codex import CodexAnswerAgent


def _agent(*, base_url: str | None = None, api_key: str | None = None) -> CodexAnswerAgent:
    return CodexAnswerAgent(
        model="test-model",
        timeout_seconds=10,
        max_concurrency=1,
        runtime_dir=Path(".codex-test-runtime"),
        base_url=base_url,
        api_key=api_key,
    )


def test_default_provider_uses_normal_codex_configuration() -> None:
    assert _agent()._provider_overrides() == ()


def test_custom_provider_builds_responses_api_configuration() -> None:
    agent = _agent(
        base_url="https://api.example.test/v1",
        api_key="secret-value",
    )

    assert agent._provider_overrides() == (
        'model_provider="guidepost_openai_compatible"',
        'model_providers.guidepost_openai_compatible.name="GuidePost OpenAI-compatible endpoint"',
        'model_providers.guidepost_openai_compatible.base_url="https://api.example.test/v1"',
        'model_providers.guidepost_openai_compatible.wire_api="responses"',
        'model_providers.guidepost_openai_compatible.env_key="GUIDEPOST_CODEX_PROVIDER_API_KEY"',
    )
    assert "secret-value" not in " ".join(agent._provider_overrides())


def test_local_provider_does_not_require_an_api_key() -> None:
    overrides = _agent(base_url="http://127.0.0.1:11434/v1")._provider_overrides()

    assert any('base_url="http://127.0.0.1:11434/v1"' in item for item in overrides)
    assert not any("env_key" in item for item in overrides)


def test_api_key_without_custom_endpoint_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a custom base URL"):
        _agent(api_key="secret-value")
