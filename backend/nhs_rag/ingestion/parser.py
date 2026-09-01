from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from nhs_rag.models import GuideDocument, GuideSection

PARSER_VERSION = "1"
_SPACE = re.compile(r"\s+")
_DATE_TEXT = r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})"
_LAST_REVIEWED = re.compile(rf"Page last reviewed:\s*{_DATE_TEXT}", re.I)
_NEXT_REVIEW = re.compile(rf"Next review due:\s*{_DATE_TEXT}", re.I)


def _clean_text(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def _html_fragment_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _clean_text(BeautifulSoup(value, "html.parser").get_text(" ", strip=True)) or None


def _json_ld_nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        nodes = [value]
        for nested in value.values():
            nodes.extend(_json_ld_nodes(nested))
        return nodes
    if isinstance(value, list):
        list_nodes: list[dict[str, Any]] = []
        for nested in value:
            list_nodes.extend(_json_ld_nodes(nested))
        return list_nodes
    return []


def _medical_page_metadata(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _json_ld_nodes(payload):
            node_type = node.get("@type", "")
            types = node_type if isinstance(node_type, list) else [node_type]
            if "MedicalWebPage" in types:
                return node
    return {}


SectionUrgency = Literal["emergency", "urgent", "routine", "general"]


def _urgency_for(element: Tag, heading: str) -> SectionUrgency:
    classes: list[str] = []
    current: Tag | None = element
    for _ in range(4):
        if current is None:
            break
        raw_classes = current.attrs.get("class")
        if isinstance(raw_classes, list):
            classes.extend(str(item).lower() for item in raw_classes)
        current = current.parent if isinstance(current.parent, Tag) else None
    combined = " ".join(classes + [heading.lower()])
    if any(
        phrase in combined
        for phrase in (
            "care-card--immediate",
            "immediate action",
            "call 999",
            "go to a&e",
            "emergency",
        )
    ):
        return "emergency"
    if any(
        phrase in combined
        for phrase in ("non-urgent advice", "see a gp", "speak to a gp", "pharmacist")
    ):
        return "routine"
    if any(
        phrase in combined
        for phrase in ("care-card--urgent", "urgent advice", "ask for an urgent", "nhs 111")
    ):
        return "urgent"
    return "general"


def _extract_sections(main: Tag, title: str) -> list[GuideSection]:
    for unwanted in main.select(
        "script, style, svg, form, nav, picture, figure, video, audio, iframe, noscript"
    ):
        unwanted.decompose()

    sections: list[GuideSection] = []
    heading = "Overview"
    urgency: SectionUrgency = "general"
    lines: list[str] = []

    def flush() -> None:
        nonlocal lines
        text = "\n".join(dict.fromkeys(line for line in lines if line))
        if text:
            sections.append(GuideSection(heading=heading, text=text, urgency=urgency))
        lines = []

    for element in main.find_all(["h1", "h2", "h3", "p", "li", "dt", "dd"]):
        if not isinstance(element, Tag):
            continue
        if element.name == "p" and element.find_parent("li") is not None:
            continue
        if element.name in {"dt", "dd"} and element.find_parent(element.name) is not None:
            continue
        text = _clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if element.name in {"h1", "h2", "h3"}:
            if element.name == "h1" and text.casefold() == title.casefold():
                continue
            flush()
            heading = text
            urgency = _urgency_for(element, heading)
            continue
        prefix = "• " if element.name in {"li", "dt", "dd"} else ""
        lines.append(prefix + text)
        candidate = _urgency_for(element, heading)
        rank = {"general": 0, "routine": 1, "urgent": 2, "emergency": 3}
        if rank[candidate] > rank[urgency]:
            urgency = candidate

    flush()
    return [
        section
        for section in sections
        if len(section.text) >= 20
        and not section.heading.casefold().startswith(("video:", "audio:"))
    ]


def parse_nhs_page(
    html: str,
    *,
    requested_url: str,
    fetched_at: datetime | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> GuideDocument:
    """Turn one server-rendered NHS page into a text-only, section-aware document."""

    soup = BeautifulSoup(html, "html.parser")
    metadata = _medical_page_metadata(soup)
    canonical_tag = soup.select_one('link[rel="canonical"]')
    canonical_candidate = (
        canonical_tag.get("href") if isinstance(canonical_tag, Tag) else metadata.get("url")
    )
    canonical_url = urljoin(requested_url, str(canonical_candidate or requested_url))
    main = soup.select_one("main#maincontent") or soup.select_one("main")
    if not isinstance(main, Tag):
        raise ValueError("NHS page did not contain a main content region")

    h1 = main.find("h1")
    title = _clean_text(h1.get_text(" ", strip=True)) if isinstance(h1, Tag) else ""
    title = title or _clean_text(str(metadata.get("name", "")))
    if not title:
        raise ValueError("NHS page did not contain a title")

    sections = _extract_sections(main, title)
    if not sections:
        raise ValueError("NHS page did not contain extractable guidance")

    review_text = soup.get_text(" ", strip=True)
    last_reviewed_match = _LAST_REVIEWED.search(review_text)
    next_review_match = _NEXT_REVIEW.search(review_text)
    description = _html_fragment_text(metadata.get("description"))
    stable_content = json.dumps(
        [section.model_dump() for section in sections], sort_keys=True, ensure_ascii=False
    )

    return GuideDocument(
        requested_url=HttpUrl(requested_url),
        canonical_url=HttpUrl(canonical_url),
        title=title,
        description=description,
        fetched_at=fetched_at or datetime.now(UTC),
        date_modified=str(metadata.get("dateModified")) if metadata.get("dateModified") else None,
        last_reviewed=(
            _clean_text(last_reviewed_match.group(1)) if last_reviewed_match else None
        ),
        next_review_due=_clean_text(next_review_match.group(1)) if next_review_match else None,
        etag=etag,
        last_modified=last_modified,
        content_sha256=hashlib.sha256(stable_content.encode()).hexdigest(),
        parser_version=PARSER_VERSION,
        sections=sections,
    )
