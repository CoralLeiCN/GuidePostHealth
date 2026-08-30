from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import HttpUrl

from nhs_rag.agent.codex import AnswerAgent
from nhs_rag.models import (
    AgentDraft,
    ChatRequest,
    ChatResponse,
    EvidenceStatement,
    RetrievedChunk,
    SourceCitation,
)
from nhs_rag.retrieval.service import RagService
from nhs_rag.safety.urgency import safety_floor


def _excerpt(text: str, limit: int = 360) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", maxsplit=1)[0]
    return f"{cut}…"


class ChatService:
    def __init__(
        self,
        *,
        rag: RagService,
        agent: AnswerAgent,
        top_k: int,
        maximum_evidence_chunks: int,
    ) -> None:
        self.rag = rag
        self.agent = agent
        self.top_k = top_k
        self.maximum_evidence_chunks = maximum_evidence_chunks

    async def answer(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid4())
        floor = safety_floor(request.message)
        if floor.emergency:
            return self._emergency_response(request_id, floor.reason)

        evidence = await asyncio.to_thread(
            self.rag.search,
            request.message,
            top_k=self.top_k,
            maximum=self.maximum_evidence_chunks,
        )
        try:
            draft = await self.agent.answer(
                question=request.message,
                history=request.history,
                evidence=evidence,
            )
            mode: Literal["codex", "retrieval_only"] = "codex"
        except Exception:
            draft = self._retrieval_fallback(evidence)
            mode = "retrieval_only"

        referenced_ids = {
            evidence_id
            for statement in [*draft.next_steps, *draft.warning_signs]
            for evidence_id in statement.evidence_ids
        }
        sources = self._citations(
            [chunk for chunk in evidence if not referenced_ids or chunk.id in referenced_ids]
        )
        return ChatResponse(
            request_id=request_id,
            mode=mode,
            grounded=bool(sources),
            urgency=draft.help_level,
            summary=draft.summary,
            next_steps=[statement.text for statement in draft.next_steps],
            warning_signs=[statement.text for statement in draft.warning_signs],
            follow_up_question=draft.follow_up_question,
            sources=sources,
            notice=(
                "AI-generated guidance based on retrieved NHS information. It is not a diagnosis."
                if mode == "codex"
                else "Extracts from retrieved NHS guidance. This is not a diagnosis."
            ),
        )

    @staticmethod
    def _retrieval_fallback(evidence: list[RetrievedChunk]) -> AgentDraft:
        general = [
            chunk for chunk in evidence if chunk.urgency not in {"emergency", "urgent"}
        ]
        warnings = [
            chunk for chunk in evidence if chunk.urgency in {"emergency", "urgent"}
        ]
        return AgentDraft(
            summary=(
                "I found NHS guidance that may be relevant, but the answer agent was not "
                "available, so I am showing source extracts instead of personalised guidance."
            ),
            help_level="unknown",
            next_steps=[
                EvidenceStatement(text=_excerpt(chunk.text), evidence_ids=[chunk.id])
                for chunk in general[:3]
            ],
            warning_signs=[
                EvidenceStatement(text=_excerpt(chunk.text), evidence_ids=[chunk.id])
                for chunk in warnings[:3]
            ],
        )

    @staticmethod
    def _citations(evidence: list[RetrievedChunk]) -> list[SourceCitation]:
        citations: list[SourceCitation] = []
        seen: set[tuple[str, str]] = set()
        for chunk in evidence:
            key = (str(chunk.url), chunk.heading)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                SourceCitation(
                    id=chunk.id,
                    title=chunk.title,
                    section=chunk.heading,
                    url=chunk.url,
                    fetched_at=chunk.fetched_at,
                    excerpt=_excerpt(chunk.text, 220),
                )
            )
        return citations[:6]

    @staticmethod
    def _emergency_response(request_id: str, reason: str | None) -> ChatResponse:
        detail = f" because you mentioned {reason}" if reason else ""
        return ChatResponse(
            request_id=request_id,
            mode="emergency",
            grounded=True,
            urgency="emergency",
            summary=(
                "This may need emergency help"
                f"{detail}. Call 999 now or go to A&E. Do not wait for an online answer."
            ),
            next_steps=["Call 999 now, or ask someone nearby to call for you."],
            warning_signs=[],
            sources=[
                SourceCitation(
                    id="nhs-999",
                    title="When to call 999",
                    section="Call 999 in a medical emergency",
                    url=HttpUrl(
                        "https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-call-999/"
                    ),
                    fetched_at=datetime.now(UTC),
                    excerpt="Use 999 for a life-threatening emergency.",
                )
            ],
            notice="Fixed safety message. Use official emergency services now.",
        )
