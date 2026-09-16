from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nhs_rag.agent.codex import CodexAnswerAgent
from nhs_rag.agent.errors import AnswerUnavailableError, InvalidAnswerError
from openai_codex import TransportClosedError


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__.return_value = client
    monkeypatch.setattr("openai_codex.AsyncCodex", lambda **kwargs: client)
    return client


def _agent(tmp_path: Path) -> CodexAnswerAgent:
    return CodexAnswerAgent(
        model="test",
        timeout_seconds=5,
        max_concurrency=1,
        runtime_dir=tmp_path,
    )


@pytest.mark.parametrize("output", [None, "not JSON", '{"summary":"uncited summary"}'])
async def test_invalid_model_output_is_an_explicit_contract_error(
    tmp_path: Path,
    runtime: AsyncMock,
    output: str | None,
) -> None:
    runtime.thread_start.return_value.run.return_value = SimpleNamespace(final_response=output)
    with pytest.raises(InvalidAnswerError):
        await _agent(tmp_path).answer(question="cough", history=[], evidence=[])


@pytest.mark.parametrize("error", [TransportClosedError("offline"), TimeoutError(), OSError()])
async def test_runtime_failures_are_translated_at_the_sdk_boundary(
    tmp_path: Path,
    runtime: AsyncMock,
    error: Exception,
) -> None:
    runtime.__aenter__.side_effect = error
    with pytest.raises(AnswerUnavailableError) as caught:
        await _agent(tmp_path).answer(question="cough", history=[], evidence=[])
    assert caught.value.__cause__ is error


async def test_sdk_adapter_does_not_swallow_programming_errors(
    tmp_path: Path,
    runtime: AsyncMock,
) -> None:
    runtime.thread_start.side_effect = AttributeError("bug")
    with pytest.raises(AttributeError, match="bug"):
        await _agent(tmp_path).answer(question="cough", history=[], evidence=[])
