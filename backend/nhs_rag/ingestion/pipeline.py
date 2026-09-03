from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from nhs_rag.ingestion.parser import parse_nhs_page
from nhs_rag.models import GuideDocument

ROBOTS_URL = "https://www.nhs.uk/robots.txt"


@dataclass(frozen=True)
class SourceSpec:
    title: str
    url: str


@dataclass
class IngestionReport:
    fetched: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def validate_nhs_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.nhs.uk":
        raise ValueError(f"Only exact https://www.nhs.uk URLs are allowed: {url}")
    if not parsed.path.startswith(("/symptoms/", "/conditions/")):
        raise ValueError(f"URL is outside the curated guidance paths: {url}")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError(f"URL contains disallowed authority components: {url}")


def load_sources(path: Path) -> list[SourceSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = [SourceSpec(**item) for item in payload["sources"]]
    for source in sources:
        validate_nhs_url(source.url)
    return sources


def source_filename(source: SourceSpec) -> str:
    slug = urlparse(source.url).path.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return f"{slug}.json"


def _load_existing(path: Path) -> GuideDocument | None:
    if not path.exists():
        return None
    try:
        return GuideDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


async def _robots_parser(client: httpx.AsyncClient, user_agent: str) -> RobotFileParser:
    response = await client.get(ROBOTS_URL, headers={"User-Agent": user_agent})
    response.raise_for_status()
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(response.text.splitlines())
    return parser


async def _request_with_retries(
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
            for previous in (*response.history, response):
                validate_nhs_url(str(previous.url))
            if response.status_code == 429:
                retry_after = min(float(response.headers.get("Retry-After", "2")), 30.0)
                await asyncio.sleep(retry_after)
                continue
            if response.status_code >= 500:
                response.raise_for_status()
            return response
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}") from last_error


async def ingest_sources(
    sources: list[SourceSpec],
    *,
    output_dir: Path,
    contact: str,
    delay_seconds: float = 1.0,
    force: bool = False,
) -> IngestionReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    user_agent = f"GuidePostHealthRAG/0.1 (+{contact})"
    report = IngestionReport()
    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"Accept": "text/html,application/xhtml+xml"},
    ) as client:
        robots = await _robots_parser(client, user_agent)
        for index, source in enumerate(sources):
            destination = output_dir / source_filename(source)
            try:
                if not robots.can_fetch(user_agent, source.url):
                    raise PermissionError(f"robots.txt does not allow {source.url}")
                existing = _load_existing(destination)
                headers = {"User-Agent": user_agent}
                if existing and existing.etag and not force:
                    headers["If-None-Match"] = existing.etag
                if existing and existing.last_modified and not force:
                    headers["If-Modified-Since"] = existing.last_modified

                response = await _request_with_retries(client, source.url, headers=headers)
                if response.status_code == 304:
                    report.unchanged += 1
                else:
                    response.raise_for_status()
                    document = parse_nhs_page(
                        response.text,
                        requested_url=source.url,
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                    )
                    temporary = destination.with_suffix(".json.tmp")
                    temporary.write_text(
                        document.model_dump_json(indent=2), encoding="utf-8"
                    )
                    temporary.replace(destination)
                    report.fetched += 1
            except Exception as exc:  # keep refreshing other reviewed sources
                report.failed += 1
                assert report.errors is not None
                report.errors.append(f"{source.title}: {exc}")
            if delay_seconds and index + 1 < len(sources):
                await asyncio.sleep(delay_seconds)

    return report
