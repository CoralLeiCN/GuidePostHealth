from __future__ import annotations

import asyncio
import json
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag

from cronjobs.nhs_dataset.content import require_main_content
from cronjobs.nhs_dataset.downloader import ROBOTS_URL, validate_nhs_url

SYMPTOMS_INDEX_URL = "https://www.nhs.uk/symptoms/"
_SPACE = re.compile(r"\s+")
_CROSS_REFERENCE = re.compile(r"^(?P<term>.+?),\s*see\s+(?P<target>.+)$", re.I)


@dataclass(frozen=True)
class SymptomIndexEntry:
    letter: str
    label: str
    term: str
    url: str
    cross_reference: bool


def _clean_text(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def parse_symptom_index(
    html: str, *, index_url: str = SYMPTOMS_INDEX_URL
) -> list[SymptomIndexEntry]:
    """Extract every A-to-Z term while retaining NHS cross-reference wording."""

    soup = BeautifulSoup(html, "html.parser")
    main = require_main_content(soup, url=index_url)

    current_letter: str | None = None
    entries: list[SymptomIndexEntry] = []
    for element in main.find_all(["h2", "li"]):
        if not isinstance(element, Tag):
            continue
        if element.name == "h2":
            heading = _clean_text(element.get_text(" ", strip=True)).upper()
            current_letter = heading if len(heading) == 1 and heading.isalpha() else None
            continue
        if current_letter is None:
            continue
        link = element.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        label = _clean_text(link.get_text(" ", strip=True))
        href = link.get("href")
        if not label or not isinstance(href, str):
            continue
        url = urljoin(index_url, href)
        validate_nhs_url(url)
        match = _CROSS_REFERENCE.match(label)
        term = _clean_text(match.group("term")) if match else label
        entries.append(
            SymptomIndexEntry(
                letter=current_letter,
                label=label,
                term=term,
                url=url,
                cross_reference=match is not None,
            )
        )

    if not entries:
        raise ValueError("NHS symptoms index did not contain any symptom links")
    return entries


def build_source_manifest(
    entries: list[SymptomIndexEntry], *, discovered_at: datetime | None = None
) -> dict[str, object]:
    """Group index terms by destination URL so each guide is downloaded once."""

    grouped: OrderedDict[str, list[SymptomIndexEntry]] = OrderedDict()
    for entry in entries:
        grouped.setdefault(entry.url, []).append(entry)

    sources: list[dict[str, object]] = []
    for url, url_entries in grouped.items():
        canonical_entry = next(
            (entry for entry in url_entries if not entry.cross_reference), url_entries[0]
        )
        title = canonical_entry.term
        aliases: list[str] = []
        seen_terms = {title.casefold()}
        for entry in url_entries:
            folded = entry.term.casefold()
            if folded not in seen_terms:
                aliases.append(entry.term)
                seen_terms.add(folded)
        sources.append(
            {
                "title": title,
                "url": url,
                "aliases": aliases,
                "index_terms": [entry.label for entry in url_entries],
                "index_entries": [asdict(entry) for entry in url_entries],
            }
        )

    timestamp = discovered_at or datetime.now(UTC)
    return {
        "licence": "Open Government Licence v3.0",
        "discovery_source": SYMPTOMS_INDEX_URL,
        "discovered_at": timestamp.isoformat(),
        "scope": "All guides linked from the NHS Symptoms A to Z index for England",
        "index_entry_count": len(entries),
        "unique_guide_count": len(sources),
        "sources": sources,
    }


async def _get_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    attempts: int = 3,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}") from last_error


async def discover_source_manifest(*, contact: str) -> dict[str, object]:
    user_agent = f"GuidePostHealthDataset/0.1 (+{contact})"
    timeout = httpx.Timeout(30.0, connect=10.0)
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        robots_response = await _get_with_retries(
            client, ROBOTS_URL, headers={"User-Agent": user_agent}
        )
        robots = RobotFileParser()
        robots.set_url(ROBOTS_URL)
        robots.parse(robots_response.text.splitlines())
        if not robots.can_fetch(user_agent, SYMPTOMS_INDEX_URL):
            raise PermissionError(f"robots.txt does not allow {SYMPTOMS_INDEX_URL}")
        response = await _get_with_retries(client, SYMPTOMS_INDEX_URL, headers=headers)
        validate_nhs_url(str(response.url))
        entries = parse_symptom_index(response.text)
        return build_source_manifest(entries)


def write_source_manifest(manifest: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
