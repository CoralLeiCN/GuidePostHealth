from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from cronjobs.nhs_dataset.downloader import SourceSpec, ingest_sources, validate_nhs_url
from cronjobs.nhs_dataset.parser import parse_nhs_page

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


@pytest.mark.parametrize(
    ("card_class", "heading", "expected"),
    [
        ("nhsuk-care-card--urgent", "Urgent advice: See a GP now", "urgent"),
        ("nhsuk-care-card--urgent", "Speak to a GP or pharmacist", "urgent"),
        ("nhsuk-care-card--immediate", "See a GP", "emergency"),
        ("nhsuk-care-card--non-urgent", "Non-urgent advice: See a GP if", "routine"),
        ("", "Non-urgent advice: See a GP if", "routine"),
        ("", "Urgent advice: See a GP now", "urgent"),
    ],
)
def test_care_card_severity_takes_precedence_over_routine_phrases(
    card_class: str, heading: str, expected: str
) -> None:
    html = f'''<main id="maincontent"><h1>Cough</h1><section class="{card_class}">
        <div><div><div><div><h2>{heading}</h2>
        <p>Seek help if these conditions apply to you.</p>
        </div></div></div></div></section></main>'''
    document = parse_nhs_page(html, requested_url="https://www.nhs.uk/symptoms/cough/")
    assert document.sections[0].urgency == expected


async def test_parser_upgrade_refetches_instead_of_reusing_conditional_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://www.nhs.uk/symptoms/cough/"
    html = (FIXTURES / "nhs_page.html").read_text(encoding="utf-8")
    old = parse_nhs_page(html, requested_url=url, etag="old-etag", last_modified="yesterday")
    old.parser_version = "1"
    (tmp_path / "cough.json").write_text(old.model_dump_json(), encoding="utf-8")

    async def fetch(
        self: httpx.AsyncClient, url: str, *, headers: dict[str, str]
    ) -> httpx.Response:
        if url.endswith("robots.txt"):
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", request=httpx.Request("GET", url)
            )
        assert "If-None-Match" not in headers
        assert "If-Modified-Since" not in headers
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fetch)
    report = await ingest_sources(
        [SourceSpec(title="Cough", url=url)],
        output_dir=tmp_path,
        raw_dir=tmp_path / "raw",
        contact="mailto:test@example.com",
        delay_seconds=0,
    )
    assert report.fetched == 1
    assert not report.errors
    assert '"parser_version": "4"' in (tmp_path / "cough.json").read_text()


async def test_ingestion_does_not_hide_programming_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    robots = Mock()
    robots.can_fetch.return_value = True
    monkeypatch.setattr(
        "cronjobs.nhs_dataset.downloader._robots_parser", AsyncMock(return_value=robots)
    )
    monkeypatch.setattr(
        "cronjobs.nhs_dataset.downloader._request_with_retries",
        AsyncMock(side_effect=AttributeError("bug")),
    )
    with pytest.raises(AttributeError, match="bug"):
        await ingest_sources(
            [SourceSpec(title="Cough", url="https://www.nhs.uk/symptoms/cough/")],
            output_dir=tmp_path,
            raw_dir=tmp_path / "raw",
            contact="mailto:test@example.com",
            delay_seconds=0,
        )
