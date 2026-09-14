from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx
from nhs_rag.ingestion.mayo.models import PARSER_VERSION, MayoDocument, MayoSource
from nhs_rag.ingestion.mayo.parser import parse_page, validate_url

from cronjobs.mayo_dataset.sources import load_sources as load_sources

ROBOTS_URL = "https://www.mayoclinic.org/robots.txt"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def load_existing(path: Path, source: MayoSource) -> MayoDocument | None:
    try:
        document = MayoDocument.model_validate_json(path.read_text(encoding="utf-8"))
        if (
            str(document.requested_url) == source.url
            and str(document.canonical_url) == source.url
            and document.symptom_id == source.slug
            and document.title == source.title
            and document.population == source.population
            and document.parser_version == PARSER_VERSION
        ):
            return document
    except (ValueError, OSError):
        pass
    return None


async def request(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> httpx.Response:
    for attempt in range(3):
        response = await client.get(url, headers=headers, follow_redirects=False)
        # Never send a second request to an unvalidated redirect target.
        if response.is_redirect and response.status_code != 304:
            raise ValueError(f"Redirect refused for {url}")
        if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
            try:
                delay = float(response.headers.get("Retry-After", "2"))
            except ValueError:
                delay = 2.0
            await asyncio.sleep(min(max(delay, 1.0), 30.0))
            continue
        return response
    raise RuntimeError("Request attempts exhausted")


async def ingest(
    sources: list[MayoSource],
    *,
    output_dir: Path,
    contact: str,
    snapshot_dir: Path | None = None,
    delay_seconds: float = 1.0,
    force: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    for source in sources:
        validate_url(source.url)
    if len({s.slug for s in sources}) != len(sources):
        raise ValueError("Duplicate symptom output filenames")
    results = []
    documents = []
    user_agent = f"NextStepMayoDataset/0.1 (+{contact})"
    async with httpx.AsyncClient(timeout=30, transport=transport) as client:
        robots = RobotFileParser()
        setup_error = None
        if snapshot_dir is None:
            try:
                response = await request(client, ROBOTS_URL, {"User-Agent": user_agent})
                response.raise_for_status()
                if "<html" in response.text.lower():
                    raise ValueError("robots.txt returned HTML instead of crawler rules")
                robots.parse(response.text.splitlines())
            except (httpx.HTTPError, ValueError) as exc:
                setup_error = str(exc)
        for index, source in enumerate(sources):
            destination = output_dir / "documents" / f"{source.slug}.json"
            existing = load_existing(destination, source)
            document = existing
            result = {"symptom_id": source.slug, "url": source.url, "status": "failed"}
            try:
                if snapshot_dir is not None:
                    snapshot = json.loads((snapshot_dir / f"{source.slug}.json").read_text())
                    if snapshot["requested_url"] != source.url:
                        raise ValueError("Snapshot URL does not match manifest")
                    fetched_at = datetime.fromisoformat(snapshot["fetched_at"])
                    if fetched_at.tzinfo is None:
                        raise ValueError("Snapshot timestamp must include a timezone")
                    document = parse_page(
                        snapshot["html"],
                        source=source,
                        fetched_at=fetched_at,
                        acquisition="browser_snapshot",
                    )
                else:
                    if setup_error:
                        raise ValueError(f"Cannot verify robots.txt: {setup_error}")
                    if not robots.can_fetch(user_agent, source.url):
                        raise ValueError("robots.txt disallows this source")
                    headers = {"User-Agent": user_agent, "Accept": "text/html"}
                    if existing and not force:
                        if existing.etag:
                            headers["If-None-Match"] = existing.etag
                        if existing.last_modified:
                            headers["If-Modified-Since"] = existing.last_modified
                    response = await request(client, source.url, headers)
                    if response.status_code == 304:
                        if existing is None or force:
                            raise ValueError("Unexpected 304 without a reusable cached document")
                        result["status"] = "unchanged"
                    else:
                        response.raise_for_status()
                        if "text/html" not in response.headers.get("Content-Type", ""):
                            raise ValueError("Source did not return HTML")
                        document = parse_page(
                            response.text,
                            source=source,
                            etag=response.headers.get("ETag"),
                            last_modified=response.headers.get("Last-Modified"),
                        )
                if result["status"] != "unchanged":
                    assert document is not None
                    write_atomic(destination, document.model_dump_json(indent=2) + "\n")
                    result["status"] = "fetched"
            except (ValueError, OSError, KeyError, TypeError, httpx.HTTPError) as exc:
                result["error"] = str(exc)
                document = existing
            if document is not None:
                documents.append(document)
            results.append(result)
            if snapshot_dir is None and delay_seconds > 0 and index + 1 < len(sources):
                await asyncio.sleep(delay_seconds)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "expected": len(sources),
        "available": len(documents),
        "fetched": sum(r["status"] == "fetched" for r in results),
        "unchanged": sum(r["status"] == "unchanged" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "complete": len(documents) == len(sources)
        and all(r["status"] != "failed" for r in results),
        "populations": {p: sum(d.population == p for d in documents) for p in ("adult", "child")},
        "factor_groups": sum(len(d.factor_groups) for d in documents),
        "factor_options": sum(len(g.options) for d in documents for g in d.factor_groups),
        "sources": results,
    }
    write_atomic(
        output_dir / "dataset.jsonl", "".join(d.model_dump_json() + "\n" for d in documents)
    )
    write_atomic(output_dir / "report.json", json.dumps(report, indent=2) + "\n")
    return report
