from __future__ import annotations

from datetime import UTC, datetime

from nhs_rag.models import ChatRequest, RetrievedChunk
from nhs_rag.service import ChatService
from pydantic import HttpUrl


class FailingAgent:
    enabled = False

    async def answer(self, **_: object) -> None:
        raise RuntimeError("offline")


class FakeRag:
    ready = True
    document_count = 1
    chunk_count = 2

    def __init__(self) -> None:
        self.searched = False

    def search(self, *_: object, **__: object) -> list[RetrievedChunk]:
        self.searched = True
        return [
            RetrievedChunk(
                id="f214650b-85ee-45ef-af65-e3ae43f48765",
                document_id="cough",
                title="Cough",
                heading="Things you can try",
                text="Rest and drink plenty of fluids.",
                url=HttpUrl("https://www.nhs.uk/symptoms/cough/"),
                fetched_at=datetime.now(UTC),
                urgency="general",
                score=0.8,
            ),
            RetrievedChunk(
                id="9d3c1f1c-e923-4677-914a-26e1a044dff7",
                document_id="cough",
                title="Cough",
                heading="Urgent advice",
                text="Contact NHS 111 if you feel very unwell.",
                url=HttpUrl("https://www.nhs.uk/symptoms/cough/"),
                fetched_at=datetime.now(UTC),
                urgency="urgent",
                score=0.2,
            ),
        ]


def _service(rag: FakeRag) -> ChatService:
    return ChatService(
        rag=rag,  # type: ignore[arg-type]
        agent=FailingAgent(),  # type: ignore[arg-type]
        top_k=4,
        maximum_evidence_chunks=6,
    )


async def test_emergency_floor_returns_before_retrieval() -> None:
    rag = FakeRag()
    response = await _service(rag).answer(ChatRequest(message="I have chest pain"))

    assert response.mode == "emergency"
    assert response.urgency == "emergency"
    assert "999" in response.summary
    assert not rag.searched


async def test_agent_failure_returns_labelled_source_extracts() -> None:
    rag = FakeRag()
    response = await _service(rag).answer(ChatRequest(message="I have a cough"))

    assert response.mode == "retrieval_only"
    assert response.urgency == "unknown"
    assert response.grounded
    assert response.next_steps == ["Rest and drink plenty of fluids."]
    assert response.warning_signs == ["Contact NHS 111 if you feel very unwell."]
    assert response.sources[0].title == "Cough"


async def test_obvious_negation_does_not_trigger_emergency_floor() -> None:
    rag = FakeRag()
    response = await _service(rag).answer(
        ChatRequest(message="I have a cough but I do not have chest pain")
    )

    assert response.mode == "retrieval_only"
    assert rag.searched
