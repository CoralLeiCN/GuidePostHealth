from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urljoin
from uuid import UUID

from bs4 import BeautifulSoup, Tag
from nhs_rag.ingestion.mayo.models import FactorGroup, FactorOption, MayoDocument, MayoSource
from nhs_rag.models import GuideSection
from pydantic import HttpUrl

from cronjobs.mayo_dataset.sources import validate_url as validate_url


def clean(element: Tag) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def parse_page(
    html: str,
    *,
    source: MayoSource,
    fetched_at: datetime | None = None,
    acquisition: Literal["http", "browser_snapshot"] = "http",
    etag: str | None = None,
    last_modified: str | None = None,
) -> MayoDocument:
    validate_url(source.url)
    if not source.slug.endswith(f"-{source.population}"):
        raise ValueError("Source population does not match its URL")
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"]')
    canonical_url = urljoin(source.url, str(canonical.get("href", ""))) if canonical else source.url
    validate_url(canonical_url)
    if canonical_url != source.url:
        raise ValueError("Canonical URL does not match the requested symptom")
    root = soup.select_one(".symptomchecker.step2")
    if root is None:
        raise ValueError("Missing symptom factor page (blocked, unavailable, or layout changed)")
    title = root.select_one(".check > h2")
    if title is None or clean(title) != source.title:
        raise ValueError("Page title does not match the source manifest")
    groups = []
    for fieldset in root.select(".check fieldset"):
        legend = fieldset.find("legend")
        if legend is None:
            raise ValueError("Factor group has no heading")
        options = []
        for checkbox in fieldset.select('input[type="checkbox"]'):
            input_id = checkbox.get("id")
            if not isinstance(input_id, str) or not input_id:
                raise ValueError("Factor has no input ID")
            label = fieldset.find("label", attrs={"for": input_id})
            if label is None:
                raise ValueError("Factor has no associated label")
            source_id = str(UUID(str(checkbox.get("sitecoreid", ""))))
            options.append(FactorOption(source_id=source_id, label=clean(label)))
        if len({option.source_id for option in options}) != len(options):
            raise ValueError("Duplicate factor ID in a group")
        groups.append(FactorGroup(heading=clean(legend), options=options))
    if sum(len(g.options) for g in groups) != len(root.select('input[type="checkbox"]')):
        raise ValueError("Some factors fall outside the recognized groups")
    advice = root.select_one(".info .seek")
    if advice is None:
        raise ValueError("Missing medical advice region")
    for unwanted in advice.select("script, style, nav, figure, iframe, video, audio, img"):
        unwanted.decompose()
    # Keep paragraphs, qualifiers and bullet order together, including nested advice lists.
    lines = []
    for element in advice.find_all(["h2", "h3", "h4", "p", "li"]):
        if element.find_parent(["li", "p"]) is not None:
            continue
        value = clean(element)
        if value:
            lines.append(("• " if element.name == "li" else "") + value)
    if len(lines) < 2:
        raise ValueError("Empty medical advice region")
    sections = [GuideSection(heading=lines[0], text="\n".join(lines[1:]))]
    stable = {
        "title": source.title,
        "population": source.population,
        "sections": [section.model_dump() for section in sections],
        "factor_groups": [group.model_dump() for group in groups],
    }
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
    return MayoDocument(
        requested_url=HttpUrl(source.url),
        canonical_url=HttpUrl(canonical_url),
        title=source.title,
        symptom_id=source.slug,
        population=source.population,
        fetched_at=fetched_at or datetime.now(UTC),
        content_sha256=digest,
        etag=etag,
        last_modified=last_modified,
        sections=sections,
        factor_groups=groups,
        acquisition=acquisition,
    )
