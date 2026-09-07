import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from huggingface_hub import HfApi

from cronjobs.nhs_dataset.content import UpstreamSchemaError
from cronjobs.nhs_dataset.discovery import build_source_manifest, parse_symptom_index
from cronjobs.nhs_dataset.downloader import (
    SourceSpec,
    archive_response,
    reparse_sources_from_raw,
    validate_nhs_url,
)
from cronjobs.nhs_dataset.exporter import ATTRIBUTION, OGL_URL, export_huggingface_dataset
from cronjobs.nhs_dataset.hub import download_dataset, upload_dataset
from cronjobs.nhs_dataset.hub_config import HubConfig, load_hub_config
from cronjobs.nhs_dataset.parser import parse_nhs_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parser_preserves_sections_and_urgency_while_stripping_media() -> None:
    html = (FIXTURES / "nhs_page.html").read_text(encoding="utf-8")
    document = parse_nhs_page(html, requested_url="https://www.nhs.uk/symptoms/cough/")

    assert document.title == "Cough"
    assert str(document.canonical_url) == "https://www.nhs.uk/symptoms/cough/"
    assert document.date_modified == "2026-08-01"
    assert document.last_reviewed == "1 August 2026"
    assert document.next_review_due == "1 August 2029"
    assert [section.urgency for section in document.sections] == [
        "general",
        "general",
        "urgent",
        "emergency",
    ]
    combined = " ".join(section.text for section in document.sections)
    assert "Rest and drink plenty of fluids" in combined
    assert "navigation" not in combined
    assert "Third party media" not in combined
    assert "ignoreMe" not in combined


@pytest.mark.parametrize(
    "url",
    [
        "http://www.nhs.uk/symptoms/cough/",
        "https://evil.example/symptoms/cough/",
        "https://www.nhs.uk.evil.example/symptoms/cough/",
        "https://www.nhs.uk/about-us/",
        "https://user@www.nhs.uk/symptoms/cough/",
        "https://www.nhs.uk/best-start-in-life/",
        "https://www.nhs.uk/symptoms/../best-start-in-life/",
        "https://www.nhs.uk/symptoms/%2e%2e/quit/",
    ],
)
def test_url_allowlist_rejects_unsafe_or_out_of_scope_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_nhs_url(url)


def test_url_allowlist_accepts_reviewed_guidance_paths() -> None:
    validate_nhs_url("https://www.nhs.uk/symptoms/cough/")
    validate_nhs_url("https://www.nhs.uk/conditions/back-pain/")
    validate_nhs_url(
        "https://www.nhs.uk/mental-health/feelings-symptoms-behaviours/feelings-and-symptoms/anger/"
    )
    validate_nhs_url("https://www.nhs.uk/pregnancy/common-symptoms/vaginal-bleeding/")


def test_index_discovery_deduplicates_urls_and_preserves_original_terms() -> None:
    html = """
    <main id="maincontent">
      <h2>F</h2>
      <ul>
        <li><a href="/symptoms/flatulence/">Farting (flatulence)</a></li>
        <li><a href="/symptoms/flatulence/">Flatulence, see Farting (flatulence)</a></li>
      </ul>
      <h2>W</h2>
      <ul><li><a href="/symptoms/flatulence/">Wind, see Farting (flatulence)</a></li></ul>
    </main>
    """
    entries = parse_symptom_index(html)
    manifest = build_source_manifest(entries, discovered_at=datetime(2026, 9, 5, tzinfo=UTC))

    assert manifest["index_entry_count"] == 3
    assert manifest["unique_guide_count"] == 1
    source = manifest["sources"][0]  # type: ignore[index]
    assert source["title"] == "Farting (flatulence)"
    assert source["aliases"] == ["Flatulence", "Wind"]
    assert source["index_terms"] == [
        "Farting (flatulence)",
        "Flatulence, see Farting (flatulence)",
        "Wind, see Farting (flatulence)",
    ]


def test_huggingface_export_writes_unique_guides_and_flat_sections(tmp_path: Path) -> None:
    html = (FIXTURES / "nhs_page.html").read_text(encoding="utf-8")
    document = parse_nhs_page(
        html,
        requested_url="https://www.nhs.uk/symptoms/cough/",
        fetched_at=datetime(2026, 9, 5, tzinfo=UTC),
    )
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "cough.json").write_text(document.model_dump_json(), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "licence": "Open Government Licence v3.0",
                "discovery_source": "https://www.nhs.uk/symptoms/",
                "index_entry_count": 2,
                "sources": [
                    {
                        "title": "Cough",
                        "url": "https://www.nhs.uk/symptoms/cough/",
                        "aliases": ["Coughing"],
                        "index_terms": ["Cough", "Coughing, see Cough"],
                        "index_entries": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "dataset"
    report = export_huggingface_dataset(
        manifest_path=manifest_path,
        corpus_dir=corpus_dir,
        output_dir=output_dir,
        hub_config=HubConfig(namespace="example-org", dataset_name="nhs-guides", private=True),
    )

    guide_lines = (output_dir / "data/guides.jsonl").read_text().splitlines()
    guides = [json.loads(line) for line in guide_lines]
    sections = [
        json.loads(line) for line in (output_dir / "data/sections.jsonl").read_text().splitlines()
    ]
    assert report.guides == 1
    assert report.sections == len(document.sections)
    assert guides[0]["page_heading"] == "Cough"
    assert guides[0]["terms"] == ["Cough", "Coughing"]
    assert guides[0]["index_terms"] == ["Cough", "Coughing, see Cough"]
    assert len(sections) == len(document.sections)
    dataset_card = (output_dir / "README.md").read_text()
    assert "config_name: guides" in dataset_card
    assert 'load_dataset("example-org/nhs-guides", "guides")' in dataset_card
    assert report.repository_id == "example-org/nhs-guides"
    assert guides[0]["attribution"] == ATTRIBUTION
    assert guides[0]["licence_url"] == OGL_URL
    assert guides[0]["source"] == "GuidePost Health adapted extract"
    assert sections[0]["attribution"] == ATTRIBUTION
    assert sections[0]["adaptation_notice"] == guides[0]["adaptation_notice"]
    assert "NOTICE.md" in dataset_card
    assert "Apache-2.0" in (output_dir / "NOTICE.md").read_text()
    assert "not NHS-authored" in dataset_card


def test_local_huggingface_config_accepts_username_or_organisation(tmp_path: Path) -> None:
    config_path = tmp_path / "huggingface.local.json"
    config_path.write_text(
        json.dumps(
            {"namespace": "guidepost-health", "dataset_name": "nhs-guides", "private": False}
        ),
        encoding="utf-8",
    )

    config = load_hub_config(config_path)

    assert config.repository_id == "guidepost-health/nhs-guides"
    assert config.private is False


def _write_minimal_hub_dataset(path: Path) -> None:
    (path / "data").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# Dataset\n", encoding="utf-8")
    (path / "NOTICE.md").write_text(ATTRIBUTION, encoding="utf-8")
    (path / "metadata.json").write_text(
        json.dumps({"guide_count": 1, "section_count": 1}), encoding="utf-8"
    )
    (path / "data/guides.jsonl").write_text('{"id":"guide"}\n', encoding="utf-8")
    (path / "data/sections.jsonl").write_text('{"id":"section"}\n', encoding="utf-8")


def test_hub_upload_uses_configured_dataset_and_does_not_include_raw_data(
    tmp_path: Path,
) -> None:
    dataset_dir = tmp_path / "dataset"
    _write_minimal_hub_dataset(dataset_dir)
    api = MagicMock(spec=HfApi)
    api.create_repo.return_value = "https://huggingface.co/datasets/example-org/nhs-guides"
    config = HubConfig(namespace="example-org", dataset_name="nhs-guides", private=True)

    url = upload_dataset(config=config, dataset_dir=dataset_dir, api=api)

    assert url == "https://huggingface.co/datasets/example-org/nhs-guides"
    api.create_repo.assert_called_once_with(
        "example-org/nhs-guides", repo_type="dataset", private=True, exist_ok=True
    )
    upload = api.upload_folder.call_args.kwargs
    assert upload["repo_id"] == "example-org/nhs-guides"
    assert upload["folder_path"] == dataset_dir
    assert upload["allow_patterns"] == [
        "README.md",
        "NOTICE.md",
        "metadata.json",
        "data/guides.jsonl",
        "data/sections.jsonl",
    ]


def test_hub_download_restores_only_dataset_files_without_nhs_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset_dir = tmp_path / "dataset"
    calls: list[dict[str, object]] = []

    def fake_snapshot_download(**kwargs: object) -> str:
        calls.append(kwargs)
        _write_minimal_hub_dataset(dataset_dir)
        return str(dataset_dir)

    monkeypatch.setattr("cronjobs.nhs_dataset.hub.snapshot_download", fake_snapshot_download)
    config = HubConfig(namespace="example-user", dataset_name="nhs-guides", private=False)

    result = download_dataset(config=config, dataset_dir=dataset_dir)

    assert result == dataset_dir
    assert calls == [
        {
            "repo_id": "example-user/nhs-guides",
            "repo_type": "dataset",
            "revision": "main",
            "local_dir": dataset_dir,
            "force_download": False,
            "allow_patterns": [
                "README.md",
                "NOTICE.md",
                "metadata.json",
                "data/guides.jsonl",
                "data/sections.jsonl",
            ],
        }
    ]


def test_raw_archive_can_rebuild_parsed_corpus_without_network(tmp_path: Path) -> None:
    source = SourceSpec(title="Cough", url="https://www.nhs.uk/symptoms/cough/")
    html = (FIXTURES / "nhs_page.html").read_bytes()
    fetched_at = datetime(2026, 9, 6, 9, 30, tzinfo=UTC)
    response = httpx.Response(
        200,
        content=html,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "ETag": '"raw-test"',
            "Last-Modified": "Sun, 06 Sep 2026 09:00:00 GMT",
        },
        request=httpx.Request("GET", source.url),
    )
    raw_dir = tmp_path / "raw"
    archive_response(
        source,
        response,
        raw_dir=raw_dir,
        fetched_at=fetched_at,
        user_agent="GuidePostHealthRAG/0.1 (+mailto:test@example.com)",
    )

    with gzip.open(raw_dir / "cough.html.gz", "rb") as handle:
        assert handle.read() == html
    metadata = json.loads((raw_dir / "cough.metadata.json").read_text())
    assert metadata["requested_url"] == source.url
    assert metadata["content_length"] == len(html)

    corpus_dir = tmp_path / "corpus"
    report = reparse_sources_from_raw([source], raw_dir=raw_dir, output_dir=corpus_dir)
    rebuilt = json.loads((corpus_dir / "cough.json").read_text())
    assert report.reparsed == 1
    assert report.failed == 0
    assert rebuilt["title"] == "Cough"
    assert rebuilt["fetched_at"] == "2026-09-06T09:30:00Z"
    assert rebuilt["etag"] == '"raw-test"'


@pytest.mark.parametrize(
    "canonical",
    [
        "https://third-party.example/symptoms/cough/",
        "https://www.nhs.uk/best-start-in-life/",
    ],
)
def test_parser_rejects_excluded_canonical_destinations(canonical: str) -> None:
    html = (
        (FIXTURES / "nhs_page.html")
        .read_text()
        .replace('href="https://www.nhs.uk/symptoms/cough/"', f'href="{canonical}"')
    )
    with pytest.raises(ValueError):
        parse_nhs_page(html, requested_url="https://www.nhs.uk/symptoms/cough/")


def test_parser_rejects_registered_medical_device_pages() -> None:
    with pytest.raises(ValueError, match="Medical-device"):
        parse_nhs_page(
            '<main id="maincontent"><h1>Tool</h1>'
            "<p>This is a registered medical device.</p></main>",
            requested_url="https://www.nhs.uk/conditions/tool/",
        )


def test_parser_excludes_embedded_media_fallback_text() -> None:
    html = (
        (FIXTURES / "nhs_page.html")
        .read_text()
        .replace("</main>", "<object><p>Third-party media fallback text.</p></object></main>")
    )
    document = parse_nhs_page(html, requested_url="https://www.nhs.uk/symptoms/cough/")
    assert "Third-party media" not in " ".join(s.text for s in document.sections)


def test_export_preserves_mixed_copy_dates(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sources = []
    for name, day in [("cough", 1), ("headache", 6)]:
        url = f"https://www.nhs.uk/symptoms/{name}/"
        document = parse_nhs_page(
            f'<main id="maincontent"><h1>{name}</h1>'
            "<p>Example guidance long enough to extract.</p></main>",
            requested_url=url,
            fetched_at=datetime(2026, 9, day, tzinfo=UTC),
        )
        (corpus / f"{name}.json").write_text(document.model_dump_json())
        sources.append({"title": name, "url": url})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": sources}))
    output = tmp_path / "dataset"
    export_huggingface_dataset(manifest_path=manifest, corpus_dir=corpus, output_dir=output)
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["copied_from"].startswith("2026-09-01")
    assert metadata["copied_at"].startswith("2026-09-06")
    card = (output / "README.md").read_text()
    assert "2026-09-01" in card and "2026-09-06" in card
    assert metadata["rights_review_status"] == "pending_page_level_review"


def test_hub_upload_rejects_dataset_missing_content_notice(tmp_path: Path) -> None:
    _write_minimal_hub_dataset(tmp_path)
    (tmp_path / "NOTICE.md").unlink()
    api = MagicMock(spec=HfApi)
    with pytest.raises(FileNotFoundError, match="NOTICE.md"):
        upload_dataset(config=HubConfig(namespace="example"), dataset_dir=tmp_path, api=api)
    api.create_repo.assert_not_called()
    api.upload_folder.assert_not_called()


@pytest.mark.parametrize("consumer", ["guide", "index"])
@pytest.mark.parametrize(
    "regions",
    [
        "<article>{body}</article>",
        "<main>{body}</main>",
        '<main id="changed">{body}</main>',
        '<div id="maincontent">{body}</div>',
        '<main id="maincontent">{body}</main><main id="maincontent">{body}</main>',
        '<main id="maincontent">{body}</main><main>Another region</main>',
    ],
    ids=["missing-main", "missing-id", "renamed-id", "wrong-tag", "duplicate-id", "extra-main"],
)
def test_changed_main_schema_fails_explicitly(consumer: str, regions: str) -> None:
    body = (
        "<h1>Cough</h1><p>Example guidance long enough to extract.</p>"
        '<h2>C</h2><ul><li><a href="/symptoms/cough/">Cough</a></li></ul>'
    )
    url = (
        "https://www.nhs.uk/symptoms/cough/"
        if consumer == "guide"
        else ("https://www.nhs.uk/symptoms/")
    )
    with pytest.raises(UpstreamSchemaError, match="expected exactly one main#maincontent") as exc:
        if consumer == "guide":
            parse_nhs_page(regions.format(body=body), requested_url=url)
        else:
            parse_symptom_index(regions.format(body=body), index_url=url)
    assert url in str(exc.value)
    assert "no fallback was used" in str(exc.value)


async def test_schema_error_stops_offline_export_and_preserves_previous_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cronjobs.nhs_dataset import cli

    source = SourceSpec(title="Cough", url="https://www.nhs.uk/symptoms/cough/")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"sources": [{"title": source.title, "url": source.url}]}))
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    previous = parse_nhs_page(
        (FIXTURES / "nhs_page.html").read_text(),
        requested_url=source.url,
    ).model_dump_json()
    (corpus / "cough.json").write_text(previous)
    raw = tmp_path / "raw"
    archive_response(
        source,
        httpx.Response(
            200,
            text="<main><h1>Cough</h1><p>The upstream template changed.</p></main>",
            request=httpx.Request("GET", source.url),
        ),
        raw_dir=raw,
        fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
        user_agent="test",
    )
    output = tmp_path / "dataset"
    exporter = MagicMock()
    monkeypatch.setattr(cli, "export_huggingface_dataset", exporter)
    monkeypatch.setattr(
        "sys.argv",
        [
            "nhs-dataset",
            "--from-raw",
            "--manifest-path",
            str(manifest),
            "--raw-dir",
            str(raw),
            "--corpus-dir",
            str(corpus),
            "--output-dir",
            str(output),
            "--hub-config",
            str(tmp_path / "missing-hub-config.json"),
        ],
    )
    assert await cli._run() == 1
    exporter.assert_not_called()
    assert (corpus / "cough.json").read_text() == previous
    assert not output.exists()
