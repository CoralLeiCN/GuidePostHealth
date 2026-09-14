from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from cronjobs.mayo_dataset.sources import ROBOTS_URL, MayoSource, validate_url
from cronjobs.raw_archive import archive_http_response, read_archive, write_archive


async def request(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> httpx.Response:
    for attempt in range(3):
        try:
            response = await client.get(url, headers=headers, follow_redirects=False)
        except httpx.TransportError:
            if attempt == 2:
                raise
            await asyncio.sleep(2**attempt)
            continue
        if response.is_redirect and response.status_code != 304:
            raise ValueError(f"Redirect refused; review source URL: {url}")
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 2:
                response.raise_for_status()
            try:
                delay = float(response.headers.get("Retry-After", "2"))
            except ValueError:
                delay = 2.0
            await asyncio.sleep(min(max(delay, 1), 30))
            continue
        return response
    raise RuntimeError(f"Request attempts exhausted for {url}")


def import_browser_capture(source: MayoSource, capture_dir: Path, raw_dir: Path) -> None:
    capture = json.loads((capture_dir / f"{source.slug}.json").read_text(encoding="utf-8"))
    if capture["requested_url"] != source.url:
        raise ValueError("Browser capture does not match source manifest")
    final_url = capture["final_url"]
    validate_url(final_url)
    if final_url != source.url:
        raise ValueError("Browser capture ended on a different guide")
    fetched_at = datetime.fromisoformat(capture["fetched_at"])
    if fetched_at.tzinfo is None:
        raise ValueError("Browser capture time must include a timezone")
    html = capture["html"]
    if not isinstance(html, str) or not html.rstrip().lower().endswith("</html>"):
        raise ValueError("Browser HTML is incomplete or truncated")
    soup = BeautifulSoup(html, "html.parser")
    if soup.html is None or soup.head is None or soup.body is None:
        raise ValueError(
            "A full HTML document is required; old extracted fragments are not raw pages"
        )
    write_archive(
        raw_dir=raw_dir,
        stem=source.slug,
        content=html.encode("utf-8"),
        metadata={
            "requested_url": source.url,
            "final_url": final_url,
            "redirect_chain": None,
            "status_code": None,
            "fetched_at": fetched_at.isoformat(),
            "encoding": "utf-8",
            "media_type": "text/html",
            "request_user_agent": None,
            "response_headers": {},
            "acquisition": "browser_dom",
            "content_scope": "full_document",
        },
    )


async def download_sources(
    sources: list[MayoSource],
    *,
    raw_dir: Path,
    contact: str,
    delay_seconds: float = 1.0,
    force: bool = False,
    capture_dir: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    if not sources or len({s.slug for s in sources}) != len(sources):
        raise ValueError("Expected distinct sources")
    for source in sources:
        validate_url(source.url)
    user_agent = f"GuidePostHealthDataset/0.1 (+{contact})"
    results = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=10), transport=transport
    ) as client:
        robots = RobotFileParser()
        setup_error = None
        if capture_dir is None:
            try:
                response = await request(client, ROBOTS_URL, {"User-Agent": user_agent})
                response.raise_for_status()
                if "<" in response.text:
                    raise ValueError("robots.txt did not return plain-text rules")
                robots.parse(response.text.splitlines())
            except (httpx.HTTPError, ValueError) as exc:
                setup_error = str(exc)
        for index, source in enumerate(sources):
            result = {"url": source.url, "slug": source.slug, "status": "failed"}
            try:
                if capture_dir is not None:
                    import_browser_capture(source, capture_dir, raw_dir)
                    result["status"] = "archived"
                else:
                    if setup_error:
                        raise ValueError(f"Cannot verify robots.txt: {setup_error}")
                    if not robots.can_fetch(user_agent, source.url):
                        raise ValueError("robots.txt disallows this source")
                    headers = {
                        "User-Agent": user_agent,
                        "Accept": "text/html,application/xhtml+xml",
                    }
                    existing = None
                    with suppress(ValueError, OSError, EOFError):
                        _, existing = read_archive(
                            raw_dir=raw_dir,
                            stem=source.slug,
                            requested_url=source.url,
                            validate_url=validate_url,
                        )
                    if existing and existing.get("acquisition") == "http" and not force:
                        validators = existing.get("response_headers", {})
                        if validators.get("etag"):
                            headers["If-None-Match"] = validators["etag"]
                        if validators.get("last-modified"):
                            headers["If-Modified-Since"] = validators["last-modified"]
                    response = await request(client, source.url, headers)
                    if response.status_code == 304:
                        if not existing or not any(h.startswith("If-") for h in headers):
                            raise ValueError(
                                "Unexpected 304 without a verified conditional archive"
                            )
                        result["status"] = "unchanged"
                    else:
                        response.raise_for_status()
                        media_type = response.headers.get("Content-Type", "").split(";")[0].lower()
                        if media_type not in {"text/html", "application/xhtml+xml"}:
                            raise ValueError("Source did not return HTML")
                        if not response.content:
                            raise ValueError("Source returned an empty body")
                        archive_http_response(
                            raw_dir=raw_dir,
                            stem=source.slug,
                            requested_url=source.url,
                            response=response,
                            fetched_at=datetime.now(UTC),
                            user_agent=user_agent,
                        )
                        result["status"] = "archived"
            except (ValueError, OSError, EOFError, KeyError, TypeError, httpx.HTTPError) as exc:
                result["error"] = str(exc)
            results.append(result)
            if capture_dir is None and not setup_error and index + 1 < len(sources):
                await asyncio.sleep(max(delay_seconds, 0))
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "expected": len(sources),
        "archived": sum(r["status"] == "archived" for r in results),
        "unchanged": sum(r["status"] == "unchanged" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "complete": all(r["status"] != "failed" for r in results),
        "sources": results,
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    temporary = raw_dir / "download-report.json.tmp"
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(raw_dir / "download-report.json")
    return report
