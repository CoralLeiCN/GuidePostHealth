from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Protocol

from nhs_rag.agent.prompt import build_prompt
from nhs_rag.models import AgentDraft, ChatMessage, RetrievedChunk

_CUSTOM_PROVIDER_ID = "guidepost_openai_compatible"
_CUSTOM_PROVIDER_API_KEY_ENV = "GUIDEPOST_CODEX_PROVIDER_API_KEY"


class AnswerAgent(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def answer(
        self,
        *,
        question: str,
        history: list[ChatMessage],
        evidence: list[RetrievedChunk],
    ) -> AgentDraft: ...


class CodexAnswerAgent:
    """Use the stable Python Codex SDK as a read-only, replaceable synthesizer."""

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        max_concurrency: int,
        runtime_dir: Path,
        base_url: str | None = None,
        api_key: str | None = None,
        enabled: bool = True,
    ) -> None:
        if api_key is not None and not base_url:
            raise ValueError("A custom Codex API key requires a custom base URL")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.runtime_dir = runtime_dir
        self.base_url = base_url
        self._api_key = api_key
        self._enabled = enabled
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def answer(
        self,
        *,
        question: str,
        history: list[ChatMessage],
        evidence: list[RetrievedChunk],
    ) -> AgentDraft:
        if not self.enabled:
            raise RuntimeError("Codex generation is disabled")

        from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox

        prompt = build_prompt(question=question, history=history, evidence=evidence)
        codex_config = CodexConfig(
            client_name="guidepost_health",
            client_title="GuidePost Health",
            config_overrides=self._provider_overrides(),
            env=(
                {_CUSTOM_PROVIDER_API_KEY_ENV: self._api_key} if self._api_key is not None else None
            ),
        )
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        async with self._semaphore:
            async with asyncio.timeout(self.timeout_seconds):
                async with AsyncCodex(config=codex_config) as codex:
                    thread = await codex.thread_start(
                        approval_mode=ApprovalMode.deny_all,
                        cwd=str(self.runtime_dir),
                        ephemeral=True,
                        model=self.model,
                        sandbox=Sandbox.read_only,
                    )
                    result = await thread.run(prompt)

        if result.final_response is None:
            raise ValueError("Codex did not return a final response")
        raw = result.final_response.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Codex did not return the required JSON object")
        draft = AgentDraft.model_validate_json(raw[start : end + 1])
        valid_ids = {chunk.id for chunk in evidence}
        statements = [*draft.next_steps, *draft.warning_signs]
        if any(
            not statement.evidence_ids
            or any(evidence_id not in valid_ids for evidence_id in statement.evidence_ids)
            for statement in statements
        ):
            raise ValueError("Codex returned an unsupported or unknown evidence reference")
        return draft

    def _provider_overrides(self) -> tuple[str, ...]:
        """Build per-process Codex config without changing the user's global config."""
        if self.base_url is None:
            return ()

        provider = f"model_providers.{_CUSTOM_PROVIDER_ID}"
        overrides = [
            f"model_provider={_toml_string(_CUSTOM_PROVIDER_ID)}",
            f"{provider}.name={_toml_string('GuidePost OpenAI-compatible endpoint')}",
            f"{provider}.base_url={_toml_string(self.base_url)}",
            f"{provider}.wire_api={_toml_string('responses')}",
        ]
        if self._api_key is not None:
            overrides.append(f"{provider}.env_key={_toml_string(_CUSTOM_PROVIDER_API_KEY_ENV)}")
        return tuple(overrides)


def _toml_string(value: str) -> str:
    """Encode untrusted configuration text as a TOML-compatible basic string."""
    return json.dumps(value)
