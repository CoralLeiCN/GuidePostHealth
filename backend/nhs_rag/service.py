from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from pydantic import HttpUrl

from nhs_rag.agent.codex import AnswerAgent
from nhs_rag.agent.errors import AnswerUnavailableError, InvalidAnswerError
from nhs_rag.models import (
    AgentDraft,
    ChatRequest,
    ChatResponse,
    RetrievedChunk,
    SourceCitation,
)
from nhs_rag.retrieval.service import RagService
from nhs_rag.safety.urgency import safety_floor

logger = logging.getLogger("nhs_rag")


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

        # User turns retain symptom context without feeding generated advice back into retrieval.
        query = "\n".join(
            [request.message]
            + [
                message.content
                for message in reversed(request.history[-6:])
                if message.role == "user"
            ]
        )
        evidence = await asyncio.to_thread(
            self.rag.search,
            query,
            top_k=self.top_k,
            maximum=self.maximum_evidence_chunks,
        )
        if not self.agent.enabled or not evidence:
            return self._retrieval_response(request_id, evidence)
        try:
            draft = await self.agent.answer(
                question=request.message,
                history=request.history,
                evidence=evidence,
            )
            referenced_ids = self._validate_references(draft, evidence)
        except (AnswerUnavailableError, InvalidAnswerError) as exc:
            # SDK/validation exceptions can contain symptom text. Log only types and request ID.
            logger.warning(
                "Answer fallback: request_id=%s error=%s cause=%s",
                request_id,
                type(exc).__name__,
                type(exc.__cause__).__name__ if exc.__cause__ else "none",
            )
            return self._retrieval_response(request_id, evidence)

        sources = self._citations([chunk for chunk in evidence if chunk.id in referenced_ids])
        return ChatResponse(
            request_id=request_id,
            mode="codex",
            evidence_status="references_checked",
            urgency=draft.help_level,
            summary=draft.summary,
            next_steps=[statement.text for statement in draft.next_steps],
            warning_signs=[statement.text for statement in draft.warning_signs],
            follow_up_question=draft.follow_up_question,
            sources=sources,
            notice=(
                "AI-generated guidance with checked NHS source references. The wording and "
                "urgency have not been independently verified. "
                "Not authored or approved by the NHS. "
                "This is not a diagnosis. Contains public sector information licensed under the "
                "Open Government Licence v3.0."
            ),
        )

    @staticmethod
    def _validate_references(draft: AgentDraft, evidence: list[RetrievedChunk]) -> set[str]:
        required = [
            draft.summary_evidence_ids,
            *(statement.evidence_ids for statement in [*draft.next_steps, *draft.warning_signs]),
        ]
        if draft.help_level != "unknown":
            required.append(draft.help_level_evidence_ids)
        referenced_ids = {
            evidence_id
            for group in [*required, draft.help_level_evidence_ids]
            for evidence_id in group
        }
        if any(not group for group in required) or not referenced_ids <= {c.id for c in evidence}:
            raise InvalidAnswerError("Missing or unknown evidence references")
        return referenced_ids

    def _retrieval_response(self, request_id: str, evidence: list[RetrievedChunk]) -> ChatResponse:
        general = [chunk for chunk in evidence if chunk.urgency not in {"emergency", "urgent"}][:3]
        warnings = sorted(
            (chunk for chunk in evidence if chunk.urgency in {"emergency", "urgent"}),
            key=lambda chunk: chunk.urgency != "emergency",
        )
        return ChatResponse(
            request_id=request_id,
            mode="retrieval_only",
            evidence_status="source_extracts" if evidence else "unavailable",
            summary=(
                "I could not produce a validated answer, so I am showing potentially relevant "
                "NHS source extracts instead of personalised guidance."
                if evidence
                else "I could not retrieve guidance for this question. Please use the NHS website."
            ),
            urgency="unknown",
            next_steps=[_excerpt(f"{chunk.heading}: {chunk.text}") for chunk in general],
            # Keep the action heading and all conditions together in safety extracts.
            warning_signs=[f"{chunk.heading}: {chunk.text}" for chunk in warnings],
            sources=self._citations([*general, *warnings]),
            notice=(
                "Extracts selected by GuidePost Health. Not authored or approved by the NHS. "
                "This is not a diagnosis. Contains public sector information licensed under "
                "the Open Government Licence v3.0."
            ),
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
        return citations

    @staticmethod
    def _emergency_response(request_id: str, reason: str | None) -> ChatResponse:
        detail = f" because you mentioned {reason}" if reason else ""
        return ChatResponse(
            request_id=request_id,
            mode="emergency",
            evidence_status="fixed_guidance",
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
                    fetched_at=None,
                    excerpt="Use 999 for a life-threatening emergency.",
                )
            ],
            notice="Fixed safety message. Use official emergency services now.",
        )
