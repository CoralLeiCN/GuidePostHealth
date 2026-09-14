import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from nhs_rag.ingestion.mayo.models import LICENCE, MayoSource
from nhs_rag.ingestion.mayo.parser import parse_page, validate_url
from nhs_rag.ingestion.mayo.pipeline import ROBOTS_URL, ingest, load_sources

SOURCE = MayoSource(
    title="Example symptom in adults",
    url="https://www.mayoclinic.org/symptom-checker/example-adult/related-factors/itt-20009075",
    population="adult",
)
# Synthetic text, with the fieldset and two-column markup observed on the public pages.
HTML = """
<nav>Unrelated navigation</nav><h1>Symptom Checker</h1>
<div class="symptomchecker step2">
  <div class="info"><div class="contentbox seek">
    <h2>When to seek medical advice</h2>
    <p>Example advice qualifier:</p><ul><li>Example warning</li></ul>
    <p>Another advice qualifier:</p><ul><li><p>Another warning</p></li></ul>
    <img alt="Advertising"><script>ignoreMe()</script>
  </div></div>
  <div class="check"><h2>Example symptom in adults</h2>
    <div class="form"><fieldset><legend>Example factor group</legend>
      <ul><li><input type="checkbox" id="a"
        sitecoreid="{FE458D9D-31D9-4FF0-AD12-4DCDF5921C57}">
        <label for="a">First option</label></li></ul>
      <ul><li><input type="checkbox" id="b"
        sitecoreid="{BA76C278-6A5B-4AB0-B25C-D5267D4FEC70}">
        <label for="b">Second option</label></li></ul>
    </fieldset></div>
    <div class="references"><li>Unrelated reference date 2017</li></div>
  </div>
</div><footer>Unrelated footer</footer>
"""


def test_parser_preserves_factors_advice_and_attribution() -> None:
    document = parse_page(HTML, source=SOURCE)
    assert document.title == SOURCE.title
    assert document.licence == LICENCE
    assert document.population == "adult"
    assert document.last_reviewed is None  # A bibliography date is not a review date.
    assert document.cause_mapping_status == "not_collected"
    assert document.urgency_classification == "not_performed"
    assert [o.label for o in document.factor_groups[0].options] == ["First option", "Second option"]
    assert document.factor_groups[0].options[0].source_id == "fe458d9d-31d9-4ff0-ad12-4dcdf5921c57"
    assert document.sections[0].text == (
        "Example advice qualifier:\n• Example warning\nAnother advice qualifier:\n• Another warning"
    )
    assert "Unrelated" not in document.model_dump_json()
    assert "ignoreMe" not in document.model_dump_json()


def test_hash_ignores_fetch_time_and_tracks_factors() -> None:
    first = parse_page(HTML, source=SOURCE, fetched_at=datetime(2020, 1, 1, tzinfo=UTC))
    second = parse_page(HTML, source=SOURCE)
    changed = parse_page(HTML.replace("Second option", "Changed option"), source=SOURCE)
    assert first.content_sha256 == second.content_sha256
    assert first.content_sha256 != changed.content_sha256


@pytest.mark.parametrize(
    "html",
    [
        "<html><h1>Access Denied</h1></html>",
        HTML.replace('for="a"', 'for="missing"'),
        HTML.replace("Example symptom in adults", "Wrong title"),
        HTML.replace("<legend>Example factor group</legend>", ""),
        HTML.replace('class="contentbox seek"', 'class="unknown"'),
        '<link rel="canonical" href="https://evil.example/">' + HTML,
    ],
)
def test_parser_rejects_incomplete_or_wrong_pages(html: str) -> None:
    with pytest.raises(ValueError):
        parse_page(html, source=SOURCE)


@pytest.mark.parametrize(
    "url",
    [
        SOURCE.url.replace("https:", "http:"),
        SOURCE.url.replace("www.mayoclinic.org", "www.mayoclinic.org.evil.example"),
        SOURCE.url.replace("www.mayoclinic.org", "user@www.mayoclinic.org"),
        SOURCE.url + "?page=2",
        SOURCE.url + "#fragment",
        SOURCE.url.replace("related-factors", "possible-causes"),
    ],
)
def test_url_allowlist(url: str) -> None:
    with pytest.raises(ValueError):
        validate_url(url)


def test_manifest_has_distinct_adult_and_child_files() -> None:
    sources = load_sources(Path(__file__).parents[1] / "config/mayo_sources.json")
    assert len(sources) == 45
    assert len({s.slug for s in sources}) == 45
    assert sum(s.population == "adult" for s in sources) == 28


async def test_http_refresh_and_conditional_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, text=HTML, headers={"Content-Type": "text/html", "ETag": '"v1"'})

    transport = httpx.MockTransport(handler)
    first = await ingest([SOURCE], output_dir=tmp_path, contact="test", transport=transport)
    before = (tmp_path / "dataset.jsonl").read_text()
    second = await ingest([SOURCE], output_dir=tmp_path, contact="test", transport=transport)
    assert first["fetched"] == 1
    assert second["unchanged"] == 1
    assert second["complete"]
    assert before == (tmp_path / "dataset.jsonl").read_text()


@pytest.mark.parametrize("failure", ["redirect", "blocked", "bad_html", "unexpected_304"])
async def test_http_failures_are_reported(tmp_path: Path, failure: str) -> None:
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url) == ROBOTS_URL:
            return httpx.Response(
                200,
                text="User-agent: *\n" + ("Disallow: /" if failure == "blocked" else "Allow: /"),
            )
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://evil.example/"})
        if failure == "unexpected_304":
            return httpx.Response(304)
        return httpx.Response(
            200, text="Website Unavailable", headers={"Content-Type": "text/html"}
        )

    report = await ingest(
        [SOURCE],
        output_dir=tmp_path,
        contact="test",
        transport=httpx.MockTransport(handler),
    )
    assert report["failed"] == 1
    assert not report["complete"]
    assert report["available"] == 0
    assert "https://evil.example/" not in requested
    if failure == "blocked":
        assert requested == [ROBOTS_URL]


async def test_snapshot_failure_preserves_previous_document(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    snapshot = raw / f"{SOURCE.slug}.json"
    payload = {"requested_url": SOURCE.url, "fetched_at": "2026-09-07T00:00:00Z", "html": HTML}
    snapshot.write_text(json.dumps(payload))
    first = await ingest([SOURCE], output_dir=tmp_path, snapshot_dir=raw, contact="test")
    assert first["complete"]
    original = (tmp_path / "dataset.jsonl").read_text()
    payload["requested_url"] = "https://evil.example/"
    snapshot.write_text(json.dumps(payload))
    second = await ingest([SOURCE], output_dir=tmp_path, snapshot_dir=raw, contact="test")
    assert second["failed"] == 1
    assert second["available"] == 1
    assert not second["complete"]
    assert (tmp_path / "dataset.jsonl").read_text() == original
