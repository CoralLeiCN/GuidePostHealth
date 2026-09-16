from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from nhs_rag.agent.codex import AnswerAgent
from nhs_rag.agent.errors import AnswerUnavailableError
from nhs_rag.models import AgentDraft, ChatMessage, ChatRequest, RetrievedChunk
from nhs_rag.retrieval.service import RagService
from nhs_rag.service import ChatService
from pydantic import HttpUrl


class FailingAgent:
    enabled = True

    async def answer(self, **_: object) -> AgentDraft:
        raise AnswerUnavailableError("offline")


class FakeRag:
    ready = True
    document_count = 1
    chunk_count = 2

    def __init__(self) -> None:
        self.searched = False
        self.query = ""

    def search(self, query: str, **_: object) -> list[RetrievedChunk]:
        self.searched = True
        self.query = query
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


def _service(rag: FakeRag, agent: AnswerAgent | None = None) -> ChatService:
    return ChatService(
        rag=cast(RagService, rag),
        agent=agent or FailingAgent(),
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
    assert response.sources[0].fetched_at is None


async def test_agent_failure_returns_labelled_source_extracts() -> None:
    rag = FakeRag()
    response = await _service(rag).answer(ChatRequest(message="I have a cough"))

    assert response.mode == "retrieval_only"
    assert response.urgency == "unknown"
    assert response.evidence_status == "source_extracts"
    assert response.next_steps == ["Things you can try: Rest and drink plenty of fluids."]
    assert response.warning_signs == ["Urgent advice: Contact NHS 111 if you feel very unwell."]
    assert response.sources[0].title == "Cough"
    assert "Contains public sector information" in response.notice
    assert "Not authored or approved by the NHS" in response.notice
    assert response.licence_url.endswith("/open-government-licence/version/3/")


async def test_obvious_negation_does_not_trigger_emergency_floor() -> None:
    rag = FakeRag()
    response = await _service(rag).answer(
        ChatRequest(message="I have a cough but I do not have chest pain")
    )

    assert response.mode == "retrieval_only"
    assert rag.searched


async def test_follow_up_retrieval_uses_symptom_context_but_not_generated_advice() -> None:
    rag = FakeRag()
    await _service(rag).answer(
        ChatRequest(
            message="Five days",
            history=[
                ChatMessage(role="user", content="I have a cough"),
                ChatMessage(
                    role="assistant", content="How long? An unrelated headache suggestion."
                ),
            ],
        )
    )
    assert "cough" in rag.query
    assert "Five days" in rag.query
    assert "headache" not in rag.query


async def test_expected_failure_is_logged_without_symptom_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class OfflineAgent(FailingAgent):
        async def answer(self, **_: object) -> AgentDraft:
            raise AnswerUnavailableError("sensitive symptom text") from TimeoutError("private data")

    response = await _service(FakeRag(), OfflineAgent()).answer(ChatRequest(message="a cough"))
    assert response.mode == "retrieval_only"
    assert response.request_id in caplog.text
    assert "TimeoutError" in caplog.text
    assert "sensitive symptom text" not in caplog.text
    assert "private data" not in caplog.text


async def test_programming_errors_are_not_converted_to_successful_fallbacks() -> None:
    class BrokenAgent(FailingAgent):
        async def answer(self, **_: object) -> AgentDraft:
            raise AttributeError("broken implementation")

    with pytest.raises(AttributeError, match="broken implementation"):
        await _service(FakeRag(), BrokenAgent()).answer(ChatRequest(message="a cough"))


async def test_disabled_agent_is_not_called(caplog: pytest.LogCaptureFixture) -> None:
    class DisabledAgent(FailingAgent):
        enabled = False

        async def answer(self, **_: object) -> AgentDraft:
            pytest.fail("disabled generation should not be called")

    response = await _service(FakeRag(), DisabledAgent()).answer(ChatRequest(message="a cough"))
    assert response.mode == "retrieval_only"
    assert not caplog.records


class DraftAgent:
    enabled = True

    def __init__(self, draft: AgentDraft) -> None:
        self.draft = draft

    async def answer(self, **_: object) -> AgentDraft:
        return self.draft


@pytest.mark.parametrize("invalid_field", ["summary_evidence_ids", "help_level_evidence_ids"])
@pytest.mark.parametrize("references", [[], ["not-retrieved"]])
async def test_missing_or_unknown_summary_and_urgency_references_fall_back(
    invalid_field: str, references: list[str]
) -> None:
    evidence_id = FakeRag().search("cough")[0].id
    draft = AgentDraft(
        summary="A generated answer",
        summary_evidence_ids=[evidence_id],
        help_level="routine",
        help_level_evidence_ids=[evidence_id],
    ).model_copy(update={invalid_field: references})
    response = await _service(FakeRag(), DraftAgent(draft)).answer(ChatRequest(message="a cough"))
    assert response.mode == "retrieval_only"
    assert response.summary != draft.summary


async def test_valid_references_are_labelled_without_claiming_verified_grounding() -> None:
    evidence_id = FakeRag().search("cough")[0].id
    draft = AgentDraft(summary="Relevant NHS guidance", summary_evidence_ids=[evidence_id])
    response = await _service(FakeRag(), DraftAgent(draft)).answer(ChatRequest(message="a cough"))
    assert response.mode == "codex"
    assert response.evidence_status == "references_checked"
    assert "grounded" not in response.model_dump()
    assert [source.id for source in response.sources] == [evidence_id]


async def test_empty_retrieval_is_explicit_and_does_not_call_the_agent() -> None:
    class EmptyRag(FakeRag):
        def search(self, query: str, **_: object) -> list[RetrievedChunk]:
            return []

    class UnexpectedAgent(FailingAgent):
        async def answer(self, **_: object) -> AgentDraft:
            pytest.fail("generation must not run without evidence")

    response = await _service(EmptyRag(), UnexpectedAgent()).answer(ChatRequest(message="a cough"))
    assert response.evidence_status == "unavailable"
    assert not response.sources


def test_fallback_preserves_all_safety_conditions_and_source_links() -> None:
    base = FakeRag().search("cough")[1]
    evidence = [
        base.model_copy(
            update={
                "id": f"warning-{index}",
                "heading": f"Urgent action {index}: Call NHS 111 if",
                "text": "condition " * 100 + "final qualifying condition",
            }
        )
        for index in range(8)
    ]
    response = _service(FakeRag())._retrieval_response("test", evidence)
    assert len(response.warning_signs) == len(response.sources) == 8
    assert all("Call NHS 111 if" in warning for warning in response.warning_signs)
    assert all(warning.endswith("final qualifying condition") for warning in response.warning_signs)
