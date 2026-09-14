import gzip
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from cronjobs.mayo_dataset.downloader import download_sources
from cronjobs.mayo_dataset.sources import ROBOTS_URL, MayoSource, validate_url
from cronjobs.raw_archive import read_archive

SOURCE = MayoSource(
    title="Example",
    population="adult",
    url="https://www.mayoclinic.org/symptom-checker/example-adult/related-factors/itt-20009075",
)
# No Mayo-specific extraction structure: acquisition must not depend on the guide parser.
HTML = (
    b"<html><head><title>Example</title></head><body><nav>Menu</nav>"
    b"<p>Example</p><script>x()</script></body></html>"
)


def read(raw_dir: Path) -> tuple[str, dict]:
    return read_archive(
        raw_dir=raw_dir, stem=SOURCE.slug, requested_url=SOURCE.url, validate_url=validate_url
    )


async def test_raw_http_preserves_response_and_conditional_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(
            200, content=HTML, headers={"Content-Type": "text/html", "ETag": '"v1"'}
        )

    transport = httpx.MockTransport(handler)
    first = await download_sources([SOURCE], raw_dir=tmp_path, contact="test", transport=transport)
    text, metadata = read(tmp_path)
    assert first["archived"] == 1
    assert text.encode() == HTML
    assert metadata["content_sha256"] == hashlib.sha256(HTML).hexdigest()
    assert metadata["content_length"] == len(HTML)
    assert metadata["acquisition"] == "http"
    assert metadata["response_headers"]["etag"] == '"v1"'
    second = await download_sources([SOURCE], raw_dir=tmp_path, contact="test", transport=transport)
    assert second["unchanged"] == 1
    assert read(tmp_path)[1]["fetched_at"] == metadata["fetched_at"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "download-report.json",
        "example-adult.html.gz",
        "example-adult.metadata.json",
    ]


async def test_browser_import_is_offline_and_preserves_provenance(tmp_path: Path) -> None:
    captures = tmp_path / "captures"
    captures.mkdir()
    (captures / f"{SOURCE.slug}.json").write_text(
        json.dumps(
            {
                "requested_url": SOURCE.url,
                "final_url": SOURCE.url,
                "fetched_at": "2026-09-07T01:00:00Z",
                "html": HTML.decode(),
            }
        )
    )

    def no_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Offline import attempted a request")

    raw_dir = tmp_path / "raw"
    report = await download_sources(
        [SOURCE],
        raw_dir=raw_dir,
        capture_dir=captures,
        contact="test",
        transport=httpx.MockTransport(no_network),
    )
    assert report["complete"]
    text, metadata = read(raw_dir)
    assert text.encode() == HTML
    assert metadata["fetched_at"] == "2026-09-07T01:00:00+00:00"
    assert metadata["acquisition"] == "browser_dom"
    assert metadata["status_code"] is None
    assert metadata["response_headers"] == {}
    with gzip.open(raw_dir / f"{SOURCE.slug}.html.gz", "wb") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        read(raw_dir)


@pytest.mark.parametrize("html", ["<div>Extracted fragment</div>", HTML.decode()[:-7]])
async def test_rejects_incomplete_captures(tmp_path: Path, html: str) -> None:
    (tmp_path / f"{SOURCE.slug}.json").write_text(
        json.dumps(
            {
                "requested_url": SOURCE.url,
                "final_url": SOURCE.url,
                "fetched_at": "2026-09-07T01:00:00Z",
                "html": html,
            }
        )
    )
    report = await download_sources(
        [SOURCE], raw_dir=tmp_path / "out", capture_dir=tmp_path, contact="test"
    )
    assert report["failed"] == 1
    assert not list((tmp_path / "out").glob("*.html.gz"))


@pytest.mark.parametrize("failure", ["redirect", "403", "bad_type", "304", "robots"])
async def test_failed_download_preserves_existing_archive(tmp_path: Path, failure: str) -> None:
    def good(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, content=HTML, headers={"Content-Type": "text/html"})

    await download_sources(
        [SOURCE], raw_dir=tmp_path, contact="test", transport=httpx.MockTransport(good)
    )
    before = read(tmp_path)
    requests = []

    def bad(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(
                200, text="User-agent: *\n" + ("Disallow: /" if failure == "robots" else "Allow: /")
            )
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://evil.example/"})
        if failure == "bad_type":
            return httpx.Response(200, content=b"{}", headers={"Content-Type": "application/json"})
        return httpx.Response(int(failure))

    report = await download_sources(
        [SOURCE], raw_dir=tmp_path, contact="test", transport=httpx.MockTransport(bad)
    )
    assert report["failed"] == 1
    assert read(tmp_path) == before
    assert "https://evil.example/" not in requests
    if failure == "robots":
        assert requests == [ROBOTS_URL]
