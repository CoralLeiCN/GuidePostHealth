from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

Urgency = Literal["emergency", "urgent", "routine", "self_care", "unknown"]


class GuideSection(BaseModel):
    heading: str
    text: str
    urgency: Literal["emergency", "urgent", "routine", "general"] = "general"


class GuideDocument(BaseModel):
    requested_url: HttpUrl
    canonical_url: HttpUrl
    title: str
    description: str | None = None
    fetched_at: datetime
    date_modified: str | None = None
    last_reviewed: str | None = None
    next_review_due: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_sha256: str
    parser_version: str = "1"
    licence: str = "Open Government Licence v3.0"
    sections: list[GuideSection]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=4_000)]


class ChatRequest(BaseModel):
    message: Annotated[str, Field(min_length=2, max_length=2_000)]
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)
    conversation_id: Annotated[str | None, Field(max_length=100)] = None

    @field_validator("message")
    @classmethod
    def meaningful_message(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Please describe the health question in a little more detail")
        return cleaned


class RetrievedChunk(BaseModel):
    id: str
    document_id: str
    title: str
    heading: str
    text: str
    url: HttpUrl
    fetched_at: datetime
    urgency: Literal["emergency", "urgent", "routine", "general"]
    score: float = 0.0


class EvidenceStatement(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=800)]
    evidence_ids: list[str] = Field(default_factory=list, max_length=4)


class AgentDraft(BaseModel):
    summary: Annotated[str, Field(min_length=1, max_length=1_500)]
    help_level: Urgency = "unknown"
    next_steps: list[EvidenceStatement] = Field(default_factory=list, max_length=6)
    warning_signs: list[EvidenceStatement] = Field(default_factory=list, max_length=6)
    follow_up_question: Annotated[str | None, Field(max_length=400)] = None


class SourceCitation(BaseModel):
    id: str
    title: str
    section: str
    url: HttpUrl
    fetched_at: datetime
    excerpt: str


class ChatResponse(BaseModel):
    request_id: str
    mode: Literal["codex", "retrieval_only", "emergency"]
    grounded: bool
    urgency: Urgency
    summary: str
    next_steps: list[str]
    warning_signs: list[str]
    follow_up_question: str | None = None
    sources: list[SourceCitation]
    notice: str = (
        "AI-generated guidance based on retrieved NHS information. It is not a diagnosis."
    )


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    documents: int
    chunks: int
    agent: Literal["codex", "retrieval_only"]
    embedding_model: str


class SourceSummary(BaseModel):
    title: str
    url: HttpUrl
    fetched_at: datetime
    last_reviewed: str | None = None
    sections: int
