from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from nhs_rag.models import GuideDocument, GuideSection
from nhs_rag.retrieval.service import RagService
from pydantic import HttpUrl


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
    service = RagService(
        corpus_dir=tmp_path,
        collection_name="test_guides",
        encoder=KeywordEncoder(),
    )

    service.index_corpus()
    results = service.search("I have a cough", top_k=1, maximum=3)

    assert service.document_count == 2
    assert results[0].title == "Cough"
    assert any(result.urgency == "emergency" for result in results)
    assert all(str(result.url).startswith("https://www.nhs.uk/") for result in results)
