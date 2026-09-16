from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Headers
from nhs_rag.main import create_app
from nhs_rag.models import GuideSection
from nhs_rag.retrieval.service import RagService
from nhs_rag.settings import Settings
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from .test_chat_service import FailingAgent, FakeRag
from .test_retrieval import FakeQdrantClient, KeywordEncoder, _document, _write


def test_health_and_chat_contract() -> None:
    rag = FakeRag()
    settings = Settings(codex_enabled=False)
    app = create_app(
        settings=settings,
        rag=cast(Any, rag),
        agent=cast(Any, FailingAgent()),
    )

    with TestClient(app) as client:
        health = client.get("/api/v1/health/ready")
        response = client.post("/api/v1/chat", json={"message": "I have a cough"})

    assert health.status_code == 200
    assert health.json()["documents"] == 1
    assert response.status_code == 200
    assert response.json()["mode"] == "retrieval_only"
    assert response.json()["sources"][0]["url"].startswith("https://www.nhs.uk/")


def test_chat_rejects_too_short_input() -> None:
    app = create_app(
        settings=Settings(codex_enabled=False),
        rag=cast(Any, FakeRag()),
        agent=cast(Any, FailingAgent()),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": " "})

    assert response.status_code == 422


def test_corrupt_corpus_reports_not_ready_and_logs_the_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    (tmp_path / "broken.json").write_text("{invalid", encoding="utf-8")
    app = create_app(
        settings=Settings(codex_enabled=False),
        rag=RagService(
            corpus_dir=tmp_path,
            collection_name="test",
            encoder=KeywordEncoder(),
            embedding_model="keyword-v1",
            client=cast(QdrantClient, FakeQdrantClient()),
        ),
        agent=FailingAgent(),
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.post("/api/v1/chat", json={"message": "a cough"}).status_code == 503
        emergency = client.post("/api/v1/chat", json={"message": "I cannot breathe"})
        assert emergency.status_code == 200
        assert emergency.json()["mode"] == "emergency"
    assert "broken.json" in caplog.text


@pytest.mark.parametrize(
    "failure",
    [
        ResponseHandlingException(ConnectionError("Qdrant is offline")),
        UnexpectedResponse(503, "Service Unavailable", b"", Headers()),
        AttributeError("programming error"),
    ],
)
def test_qdrant_startup_failure_keeps_emergency_guidance_available(
    tmp_path: Path, failure: Exception
) -> None:
    _write(
        tmp_path / "cough.json",
        _document(
            "Cough",
            "https://www.nhs.uk/symptoms/cough/",
            [GuideSection(heading="Overview", text="A cough often clears in a few weeks.")],
        ),
    )

    class UnavailableQdrant(FakeQdrantClient):
        def collection_exists(self, _: str) -> bool:
            raise failure

    app = create_app(
        settings=Settings(codex_enabled=False),
        rag=RagService(
            corpus_dir=tmp_path,
            collection_name="test",
            encoder=KeywordEncoder(),
            embedding_model="keyword-v1",
            client=cast(QdrantClient, UnavailableQdrant()),
        ),
        agent=FailingAgent(),
    )
    if isinstance(failure, AttributeError):
        with pytest.raises(AttributeError, match="programming error"), TestClient(app):
            pass
        return

    with TestClient(app) as client:
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.post("/api/v1/chat", json={"message": "a cough"}).status_code == 503
        emergency = client.post("/api/v1/chat", json={"message": "I cannot breathe"})
        assert emergency.status_code == 200
        assert emergency.json()["mode"] == "emergency"
