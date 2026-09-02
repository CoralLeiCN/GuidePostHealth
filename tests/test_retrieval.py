from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from nhs_rag.models import GuideDocument, GuideSection
from nhs_rag.retrieval.service import IndexUnavailableError, RagService
from pydantic import HttpUrl
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


class KeywordEncoder:
    @property
    def dimension(self) -> int:
        return 4

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            raw = [
                float(lowered.count("cough")),
                float(lowered.count("headache")),
                float(lowered.count("breathe") + lowered.count("urgent")),
                0.1,
            ]
            norm = math.sqrt(sum(value * value for value in raw))
            vectors.append([value / norm for value in raw])
        return vectors


class FakeQdrantClient:
    def __init__(self) -> None:
        self.points: dict[object, PointStruct] = {}
        self.metadata: dict[str, object] | None = None
        self.create_calls = 0

    def collection_exists(self, _: str) -> bool:
        return self.metadata is not None

    def delete_collection(self, _: str) -> bool:
        self.points.clear()
        self.metadata = None
        return True

    def create_collection(
        self, *, metadata: dict[str, object], **_: object
    ) -> bool:
        self.metadata = metadata
        self.create_calls += 1
        return True

    def upsert(self, *, points: Sequence[PointStruct], **_: object) -> None:
        for point in points:
            self.points[point.id] = point

    def count(self, _: str, **__: object) -> SimpleNamespace:
        return SimpleNamespace(count=len(self.points))

    def get_collection(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(config=SimpleNamespace(metadata=self.metadata))

    def query_points(
        self, *, query: list[float], limit: int, **_: object
    ) -> SimpleNamespace:
        scored: list[SimpleNamespace] = []
        for point in self.points.values():
            vector = cast(list[float], point.vector)
            payload = cast(dict[str, Any], point.payload)
            score = sum(left * right for left, right in zip(query, vector, strict=True))
            scored.append(SimpleNamespace(payload=payload, score=score))
        scored.sort(key=lambda point: point.score, reverse=True)
        return SimpleNamespace(points=scored[:limit])

    def close(self) -> None:
        pass


def _document(title: str, url: str, sections: list[GuideSection]) -> GuideDocument:
    return GuideDocument(
        requested_url=HttpUrl(url),
        canonical_url=HttpUrl(url),
        title=title,
        fetched_at=datetime.now(UTC),
        content_sha256="a" * 64,
        sections=sections,
    )


def _write(path: Path, document: GuideDocument) -> None:
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")


def test_qdrant_retrieval_adds_safety_sections_from_matched_guide(tmp_path: Path) -> None:
    _write(
        tmp_path / "cough.json",
        _document(
            "Cough",
            "https://www.nhs.uk/symptoms/cough/",
            [
                GuideSection(heading="Overview", text="A cough often clears in a few weeks."),
                GuideSection(
                    heading="Immediate action required",
                    text="Call 999 if you cannot breathe.",
                    urgency="emergency",
                ),
            ],
        ),
    )
    _write(
        tmp_path / "headache.json",
        _document(
            "Headaches",
            "https://www.nhs.uk/symptoms/headaches/",
            [GuideSection(heading="Overview", text="Headache guidance and self care.")],
        ),
    )
    fake_client = FakeQdrantClient()
    service = RagService(
        corpus_dir=tmp_path,
        collection_name="test_guides",
        encoder=KeywordEncoder(),
        embedding_model="keyword-v1",
        client=cast(QdrantClient, fake_client),
    )

    service.index_corpus()
    results = service.search("I have a cough", top_k=1, maximum=3)

    reloaded_service = RagService(
        corpus_dir=tmp_path,
        collection_name="test_guides",
        encoder=KeywordEncoder(),
        embedding_model="keyword-v1",
        client=cast(QdrantClient, fake_client),
    )
    reloaded_service.load_existing_index()

    assert service.document_count == 2
    assert reloaded_service.ready
    assert reloaded_service.chunk_count == service.chunk_count
    assert fake_client.create_calls == 1
    assert results[0].title == "Cough"
    assert any(result.urgency == "emergency" for result in results)
    assert all(str(result.url).startswith("https://www.nhs.uk/") for result in results)

    fake_client.metadata = {"guidepost": {"schema_version": 0}}
    with pytest.raises(IndexUnavailableError, match="does not match"):
        reloaded_service.load_existing_index()
