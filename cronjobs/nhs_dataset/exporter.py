from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from nhs_rag.models import GuideDocument

from cronjobs.nhs_dataset.downloader import (
    SourceSpec,
    load_sources,
    source_filename,
    validate_nhs_url,
)
from cronjobs.nhs_dataset.hub_config import HubConfig

OGL_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
NHS_TERMS_URL = "https://www.nhs.uk/our-policies/terms-and-conditions/"
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
ADAPTATION_NOTICE = (
    "Adapted text extracts produced by GuidePost Health; not NHS-authored or clinically approved. "
    "Original page links identify provenance, not authorship of this adaptation. "
    "Content is incomplete: media, tables and some context are omitted; "
    "urgency labels are unvalidated parsing heuristics. Consult the original pages."
)


@dataclass(frozen=True)
class DatasetExportReport:
    guides: int
    sections: int
    output_dir: Path
    repository_id: str | None


def _document_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def _load_document(source: SourceSpec, corpus_dir: Path) -> GuideDocument:
    path = corpus_dir / source_filename(source)
    if not path.exists():
        raise FileNotFoundError(f"Missing downloaded guide for {source.title}: {path}")
    return GuideDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _source_metadata(manifest: dict[str, Any], url: str) -> dict[str, Any]:
    for item in manifest["sources"]:
        if item["url"] == url:
            return cast(dict[str, Any], item)
    raise KeyError(url)


def _guide_record(
    source: SourceSpec, document: GuideDocument, source_metadata: dict[str, Any]
) -> dict[str, Any]:
    canonical_url = str(document.canonical_url)
    sections = [section.model_dump(mode="json") for section in document.sections]
    terms = list(dict.fromkeys([source.title, document.title, *source.aliases]))
    return {
        "id": _document_id(canonical_url),
        "title": source.title,
        "page_heading": document.title,
        "terms": terms,
        "aliases": list(source.aliases),
        "index_terms": list(source.index_terms),
        "index_entries": source_metadata.get("index_entries", []),
        "url": str(document.requested_url),
        "canonical_url": canonical_url,
        "description": document.description,
        "text": "\n\n".join(
            f"{section.heading}\n{section.text}" for section in document.sections
        ),
        "sections": sections,
        "language": "en",
        "geographic_scope": "England",
        "source": "GuidePost Health adapted extract",
        "original_publisher": "NHS website",
        "attribution": ATTRIBUTION,
        "adaptation_notice": ADAPTATION_NOTICE,
        "licence_url": OGL_URL,
        "terms_url": NHS_TERMS_URL,
        "licence": document.licence,
        "fetched_at": document.fetched_at.isoformat(),
        "date_modified": document.date_modified,
        "last_reviewed": document.last_reviewed,
        "next_review_due": document.next_review_due,
        "content_sha256": document.content_sha256,
        "parser_version": document.parser_version,
    }


def _section_records(guide: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, section in enumerate(guide["sections"]):
        records.append(
            {
                "id": f"{guide['id']}:{index}",
                "guide_id": guide["id"],
                "title": guide["title"],
                "terms": guide["terms"],
                "aliases": guide["aliases"],
                "url": guide["url"],
                "canonical_url": guide["canonical_url"],
                "heading": section["heading"],
                "text": section["text"],
                "urgency": section["urgency"],
                "language": guide["language"],
                "geographic_scope": guide["geographic_scope"],
                "source": guide["source"],
                "original_publisher": guide["original_publisher"],
                "attribution": guide["attribution"],
                "adaptation_notice": guide["adaptation_notice"],
                "licence_url": guide["licence_url"],
                "terms_url": guide["terms_url"],
                "licence": guide["licence"],
                "fetched_at": guide["fetched_at"],
                "last_reviewed": guide["last_reviewed"],
                "content_sha256": guide["content_sha256"],
            }
        )
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def _dataset_card(
    *, guides: int, sections: int, copied_from: str, copied_at: str, repository_id: str | None
) -> str:
    load_target = repository_id or "YOUR_ACCOUNT/YOUR_DATASET"
    return f"""---
pretty_name: NHS Symptoms A to Z Guides
language:
- en
license: other
license_name: Open Government Licence v3.0
license_link: {OGL_URL}
size_categories:
- 1K<n<10K
tags:
- medical
- health
- nhs
- public-health
configs:
- config_name: guides
  default: true
  data_files:
  - split: train
    path: data/guides.jsonl
- config_name: sections
  data_files:
  - split: train
    path: data/sections.jsonl
---

# NHS Symptoms A to Z Guides

An independently produced collection of adapted text extracts from {guides} guidance pages
linked from the [original Symptoms A to Z index](https://www.nhs.uk/symptoms/).
Original pages were fetched between {copied_from} and {copied_at}; each row records its own
fetch time. This is a historical snapshot, not a live or complete copy of the original pages.
The source index contains multiple medical and everyday names for some pages. The `guides`
configuration stores each destination page once while retaining those names in `terms`,
`aliases`, `index_terms`, and `index_entries`. `title` is the canonical A-to-Z label and
`page_heading` preserves the guide's extracted H1. The `sections` configuration contains
{sections} ordered sections for retrieval applications.

## Licence and attribution

{ATTRIBUTION}

{ADAPTATION_NOTICE}

This dataset is independent and is not affiliated with, approved or endorsed by the NHS.
Every row contains original-page provenance links and the original fetch timestamp.

The underlying eligible text is licensed under the
[Open Government Licence v3.0]({OGL_URL}). Reuse remains subject to the
[NHS website terms and conditions]({NHS_TERMS_URL}), including excluded content, attribution,
freshness, and no-endorsement requirements. This export excludes logos, images, video, audio,
forms, interactive medical-device functionality, navigation, scripts, and styles.
Removing these elements does not establish clearance for all third-party text. Page-level
rights review remains required; the licence label is not a rights-clearance certificate.
The software's Apache-2.0 licence does not replace the content licence. See `NOTICE.md`.

## Intended use and limitations

This corpus supports local LLM testing and learning retrieval-augmented generation (RAG).
GuidePost Health is not designed or intended for any public use, personal health guidance
or clinical use. Use fictional test questions, not real patient information. Public or
clinical applications would require a separate scope decision and appropriate privacy,
clinical and other reviews; they are not planned releases of this learning project.
This intended-use statement does not change the underlying OGL licence.
Section `urgency`
labels are structural parsing heuristics and have not been clinically validated. The full
source text and current urgency advice should be checked at the linked NHS page before use.

The NHS terms require an unchanged copy either to show when it was copied or to be refreshed
at least every 7 days; they recommend refreshing every 24 hours. Adaptation or stale content
can invalidate formal clinical approval. These adapted records use the generic OGL
attribution; do not label them as unchanged NHS-authored information. Preserve this notice,
licence link, original-page links and per-record dates in downstream copies and applications.
General commercial reuse is permitted subject to the terms, but NHS terms section 3.10
prohibits a specific charge for access to NHS content. No patient records are included;
processing users' health information requires separate privacy and data-protection compliance.

## Loading

```python
from datasets import load_dataset

guides = load_dataset("{load_target}", "guides")
sections = load_dataset("{load_target}", "sections")
```

The split is named `train` only for compatibility with standard dataset loaders. The records
are an unsplit reference corpus and are not a recommendation to train a medical model.

## Generation

Generated by GuidePost Health from server-rendered NHS HTML. The pipeline checks robots.txt,
uses a sequential rate-limited downloader, validates redirects, strips excluded media and
interactive elements, retains source and review metadata, and hashes parsed content.
"""


def export_huggingface_dataset(
    *,
    manifest_path: Path,
    corpus_dir: Path,
    output_dir: Path,
    hub_config: HubConfig | None = None,
) -> DatasetExportReport:
    resolved_hub_config = hub_config or HubConfig()
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = load_sources(manifest_path)
    guides: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for source in sources:
        document = _load_document(source, corpus_dir)
        canonical_url = str(document.canonical_url)
        validate_nhs_url(canonical_url)
        if str(document.requested_url) != source.url:
            raise ValueError(f"Downloaded guide does not match manifest: {source.url}")
        if document.licence != "Open Government Licence v3.0":
            raise ValueError(f"Unexpected content licence for {source.url}")
        if canonical_url in seen_urls:
            raise ValueError(f"Duplicate canonical guide URL in corpus: {canonical_url}")
        seen_urls.add(canonical_url)
        guides.append(_guide_record(source, document, _source_metadata(manifest, source.url)))

    sections = [record for guide in guides for record in _section_records(guide)]
    copied_at = max(guide["fetched_at"] for guide in guides)
    copied_from = min(guide["fetched_at"] for guide in guides)
    _write_jsonl(output_dir / "data" / "guides.jsonl", guides)
    _write_jsonl(output_dir / "data" / "sections.jsonl", sections)
    (output_dir / "README.md").write_text(
        _dataset_card(
            guides=len(guides),
            sections=len(sections),
            copied_from=copied_from,
            copied_at=copied_at,
            repository_id=resolved_hub_config.repository_id,
        ),
        encoding="utf-8",
    )
    (output_dir / "NOTICE.md").write_text(
        f"# Content reuse notice\n\n{ATTRIBUTION}\n\n{OGL_URL}\n\n"
        f"{ADAPTATION_NOTICE}\n\nReuse is subject to {NHS_TERMS_URL}\n\n"
        "NHS logos, media, third-party rights, personal data and medical devices are not "
        "licensed by this notice. No NHS affiliation, approval or endorsement is implied. "
        "Apache-2.0 applies to project software, not the underlying NHS content.\n",
        encoding="utf-8",
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "guide_count": len(guides),
                "section_count": len(sections),
                "index_entry_count": manifest.get("index_entry_count"),
                "copied_at": copied_at,
                "copied_from": copied_from,
                "attribution": ATTRIBUTION,
                "adaptation_notice": ADAPTATION_NOTICE,
                "licence_url": OGL_URL,
                "terms_url": NHS_TERMS_URL,
                "rights_review_status": "pending_page_level_review",
                "intended_use": (
                    "Local LLM testing and RAG learning; not designed for public or clinical use"
                ),
                "discovery_source": manifest.get("discovery_source"),
                "licence": manifest.get("licence"),
                "huggingface_repository_id": resolved_hub_config.repository_id,
                "huggingface_private": resolved_hub_config.private,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return DatasetExportReport(
        guides=len(guides),
        sections=len(sections),
        output_dir=output_dir,
        repository_id=resolved_hub_config.repository_id,
    )
