from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from nhs_rag.agent.prompt import build_prompt
from nhs_rag.models import AgentDraft, ChatMessage, RetrievedChunk


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
        enabled: bool = True,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.runtime_dir = runtime_dir
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

        from openai_codex import ApprovalMode, AsyncCodex, Sandbox

        prompt = build_prompt(question=question, history=history, evidence=evidence)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        async with self._semaphore:
            async with asyncio.timeout(self.timeout_seconds):
                async with AsyncCodex() as codex:
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
