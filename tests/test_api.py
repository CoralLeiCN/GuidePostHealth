from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient
from nhs_rag.main import create_app
from nhs_rag.settings import Settings

from .test_chat_service import FailingAgent, FakeRag


def test_health_and_chat_contract() -> None:
    rag = FakeRag()
    settings = Settings(auto_index=False, codex_enabled=False)
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
        settings=Settings(auto_index=False, codex_enabled=False),
        rag=cast(Any, FakeRag()),
        agent=cast(Any, FailingAgent()),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"message": " "})

    assert response.status_code == 422
