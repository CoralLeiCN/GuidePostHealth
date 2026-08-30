from pathlib import Path

import pytest
from nhs_rag.ingestion.parser import parse_nhs_page
from nhs_rag.ingestion.pipeline import validate_nhs_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_parser_preserves_sections_and_urgency_while_stripping_media() -> None:
    html = (FIXTURES / "nhs_page.html").read_text(encoding="utf-8")
    document = parse_nhs_page(html, requested_url="https://www.nhs.uk/symptoms/cough/")

    assert document.title == "Cough"
    assert str(document.canonical_url) == "https://www.nhs.uk/symptoms/cough/"
    assert document.date_modified == "2026-08-01"
    assert document.last_reviewed == "1 August 2026"
    assert document.next_review_due == "1 August 2029"
    assert [section.urgency for section in document.sections] == [
        "general",
        "general",
        "urgent",
        "emergency",
    ]
    combined = " ".join(section.text for section in document.sections)
    assert "Rest and drink plenty of fluids" in combined
    assert "navigation" not in combined
    assert "Third party media" not in combined
    assert "ignoreMe" not in combined


@pytest.mark.parametrize(
    "url",
    [
        "http://www.nhs.uk/symptoms/cough/",
        "https://evil.example/symptoms/cough/",
        "https://www.nhs.uk.evil.example/symptoms/cough/",
        "https://www.nhs.uk/about-us/",
        "https://user@www.nhs.uk/symptoms/cough/",
    ],
)
def test_url_allowlist_rejects_unsafe_or_out_of_scope_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_nhs_url(url)


def test_url_allowlist_accepts_reviewed_guidance_paths() -> None:
    validate_nhs_url("https://www.nhs.uk/symptoms/cough/")
    validate_nhs_url("https://www.nhs.uk/conditions/back-pain/")
