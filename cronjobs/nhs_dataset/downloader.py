from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from nhs_rag.models import GuideDocument

from cronjobs.nhs_dataset.parser import parse_nhs_page
from cronjobs.nhs_dataset.urls import validate_nhs_url as validate_nhs_url

ROBOTS_URL = "https://www.nhs.uk/robots.txt"
RAW_ARCHIVE_VERSION = "1"


@dataclass(frozen=True)
class SourceSpec:
    title: str
    url: str
    aliases: tuple[str, ...] = ()
    index_terms: tuple[str, ...] = ()


@dataclass
class IngestionReport:
    fetched: int = 0
    archived: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


@dataclass
class ReparseReport:
    reparsed: int = 0
    failed: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def load_sources(path: Path) -> list[SourceSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = [
        SourceSpec(
            title=item["title"],
            url=item["url"],
            aliases=tuple(item.get("aliases", ())),
            index_terms=tuple(item.get("index_terms", ())),
        )
        for item in payload["sources"]
    ]
    for source in sources:
        validate_nhs_url(source.url)
    return sources


def _source_slug(source: SourceSpec) -> str:
    slug = urlparse(source.url).path.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if not slug:
        raise ValueError(f"Source URL does not have a filename-safe slug: {source.url}")
    return slug


def source_filename(source: SourceSpec) -> str:
    return f"{_source_slug(source)}.json"


def raw_html_filename(source: SourceSpec) -> str:
    return f"{_source_slug(source)}.html.gz"


def raw_metadata_filename(source: SourceSpec) -> str:
    return f"{_source_slug(source)}.metadata.json"


def _load_existing(path: Path) -> GuideDocument | None:
    if not path.exists():
        return None
    try:
        return GuideDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _write_document(document: GuideDocument, destination: Path) -> None:
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(destination)


def _raw_snapshot_exists(source: SourceSpec, raw_dir: Path) -> bool:
    return (raw_dir / raw_html_filename(source)).exists() and (
        raw_dir / raw_metadata_filename(source)
    ).exists()


def archive_response(
    source: SourceSpec,
    response: httpx.Response,
    *,
    raw_dir: Path,
    fetched_at: datetime,
    user_agent: str,
) -> None:
    """Atomically retain decoded response bytes and provenance for offline reparsing."""

    raw_dir.mkdir(parents=True, exist_ok=True)
    content = response.content
    html_path = raw_dir / raw_html_filename(source)
    html_temporary = html_path.with_name(html_path.name + ".tmp")
    with gzip.open(html_temporary, "wb", compresslevel=9) as handle:
        handle.write(content)
    html_temporary.replace(html_path)

    metadata = {
        "archive_version": RAW_ARCHIVE_VERSION,
        "requested_url": source.url,
        "final_url": str(response.url),
        "redirect_chain": [str(item.url) for item in response.history],
        "status_code": response.status_code,
        "fetched_at": fetched_at.isoformat(),
        "encoding": response.encoding or "utf-8",
        "media_type": response.headers.get("Content-Type"),
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "content_length": len(content),
        "request_user_agent": user_agent,
        "response_headers": {key.lower(): value for key, value in response.headers.items()},
    }
    metadata_path = raw_dir / raw_metadata_filename(source)
    metadata_temporary = metadata_path.with_name(metadata_path.name + ".tmp")
    metadata_temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata_temporary.replace(metadata_path)


def _load_raw_snapshot(source: SourceSpec, raw_dir: Path) -> tuple[str, dict[str, object]]:
    html_path = raw_dir / raw_html_filename(source)
    metadata_path = raw_dir / raw_metadata_filename(source)
    if not html_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(f"Raw snapshot is incomplete for {source.title}")

    metadata: dict[str, object] = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("archive_version") != RAW_ARCHIVE_VERSION:
        raise ValueError(f"Unsupported raw archive version for {source.title}")
    if metadata.get("requested_url") != source.url:
        raise ValueError(f"Raw snapshot URL does not match manifest for {source.title}")
    final_url = metadata.get("final_url")
    if not isinstance(final_url, str):
        raise ValueError(f"Raw snapshot has no final URL for {source.title}")
    validate_nhs_url(final_url)

    with gzip.open(html_path, "rb") as handle:
        content = handle.read()
    if hashlib.sha256(content).hexdigest() != metadata.get("content_sha256"):
        raise ValueError(f"Raw snapshot checksum failed for {source.title}")
    encoding = metadata.get("encoding", "utf-8")
    if not isinstance(encoding, str):
        raise ValueError(f"Raw snapshot encoding is invalid for {source.title}")
    return content.decode(encoding), metadata


def reparse_sources_from_raw(
    sources: list[SourceSpec], *, raw_dir: Path, output_dir: Path
) -> ReparseReport:
    """Rebuild parsed guide JSON entirely from the validated local raw archive."""

    output_dir.mkdir(parents=True, exist_ok=True)
    report = ReparseReport()
    for source in sources:
        try:
            html, metadata = _load_raw_snapshot(source, raw_dir)
            fetched_at_value = metadata.get("fetched_at")
            if not isinstance(fetched_at_value, str):
                raise ValueError(f"Raw snapshot fetch time is invalid for {source.title}")
            headers = metadata.get("response_headers", {})
            if not isinstance(headers, dict):
                raise ValueError(f"Raw snapshot headers are invalid for {source.title}")
            document = parse_nhs_page(
                html,
                requested_url=source.url,
                fetched_at=datetime.fromisoformat(fetched_at_value),
                etag=headers.get("etag") if isinstance(headers.get("etag"), str) else None,
                last_modified=(
                    headers.get("last-modified")
                    if isinstance(headers.get("last-modified"), str)
                    else None
                ),
            )
            _write_document(document, output_dir / source_filename(source))
            report.reparsed += 1
        except Exception as exc:
            report.failed += 1
            assert report.errors is not None
            report.errors.append(f"{source.title}: {exc}")
    return report


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
    raw_dir: Path,
    contact: str,
    delay_seconds: float = 1.0,
    force: bool = False,
) -> IngestionReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
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
                raw_exists = _raw_snapshot_exists(source, raw_dir)
                headers = {"User-Agent": user_agent}
                if existing and raw_exists and existing.etag and not force:
                    headers["If-None-Match"] = existing.etag
                if existing and raw_exists and existing.last_modified and not force:
                    headers["If-Modified-Since"] = existing.last_modified

                response = await _request_with_retries(client, source.url, headers=headers)
                if response.status_code == 304:
                    report.unchanged += 1
                else:
                    response.raise_for_status()
                    fetched_at = datetime.now(UTC)
                    archive_response(
                        source,
                        response,
                        raw_dir=raw_dir,
                        fetched_at=fetched_at,
                        user_agent=user_agent,
                    )
                    report.archived += 1
                    document = parse_nhs_page(
                        response.text,
                        requested_url=source.url,
                        fetched_at=fetched_at,
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                    )
                    _write_document(document, destination)
                    report.fetched += 1
            except Exception as exc:  # keep refreshing other reviewed sources
                report.failed += 1
                assert report.errors is not None
                report.errors.append(f"{source.title}: {exc}")
            if delay_seconds and index + 1 < len(sources):
                await asyncio.sleep(delay_seconds)

    return report
