"""Source-independent raw HTML storage shared by offline guide jobs."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

RAW_ARCHIVE_VERSION = "1"


def write_archive(*, raw_dir: Path, stem: str, content: bytes, metadata: dict[str, Any]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        **metadata,
        "archive_version": RAW_ARCHIVE_VERSION,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "content_length": len(content),
    }
    body = raw_dir / f"{stem}.html.gz"
    sidecar = raw_dir / f"{stem}.metadata.json"
    temporary = body.with_suffix(body.suffix + ".tmp")
    with gzip.open(temporary, "wb", compresslevel=9) as handle:
        handle.write(content)
    temporary.replace(body)
    temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(sidecar)


def archive_http_response(
    *,
    raw_dir: Path,
    stem: str,
    requested_url: str,
    response: httpx.Response,
    fetched_at: datetime,
    user_agent: str,
) -> None:
    write_archive(
        raw_dir=raw_dir,
        stem=stem,
        content=response.content,
        metadata={
            "requested_url": requested_url,
            "final_url": str(response.url),
            "redirect_chain": [str(item.url) for item in response.history],
            "status_code": response.status_code,
            "fetched_at": fetched_at.isoformat(),
            "encoding": response.encoding or "utf-8",
            "media_type": response.headers.get("Content-Type"),
            "request_user_agent": user_agent,
            "response_headers": {key.lower(): value for key, value in response.headers.items()},
            "acquisition": "http",
            "content_scope": "full_document",
        },
    )


def read_archive(
    *,
    raw_dir: Path,
    stem: str,
    requested_url: str,
    validate_url: Callable[[str], None],
) -> tuple[str, dict[str, Any]]:
    metadata = json.loads((raw_dir / f"{stem}.metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError(f"Raw snapshot metadata is not an object for {requested_url}")
    if metadata.get("archive_version") != RAW_ARCHIVE_VERSION:
        raise ValueError(f"Unsupported raw archive version for {requested_url}")
    if metadata.get("requested_url") != requested_url:
        raise ValueError(f"Raw snapshot URL does not match manifest for {requested_url}")
    final_url = metadata.get("final_url")
    if not isinstance(final_url, str):
        raise ValueError(f"Raw snapshot has no final URL for {requested_url}")
    validate_url(final_url)
    with gzip.open(raw_dir / f"{stem}.html.gz", "rb") as handle:
        content = handle.read()
    if hashlib.sha256(content).hexdigest() != metadata.get("content_sha256"):
        raise ValueError(f"Raw snapshot checksum failed for {requested_url}")
    if len(content) != metadata.get("content_length"):
        raise ValueError(f"Raw snapshot byte length mismatch for {requested_url}")
    encoding = metadata.get("encoding", "utf-8")
    if not isinstance(encoding, str):
        raise ValueError(f"Raw snapshot encoding is invalid for {requested_url}")
    return content.decode(encoding), metadata
