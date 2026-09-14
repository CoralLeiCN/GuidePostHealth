# Corpus and RAG specification

The detailed [dataset creation workflow and extraction specification](nhs-dataset-workflow.md)
is the reference for commands, raw/parsed/export schemas, selector behavior, multimedia loss,
failure handling and human review. This document summarizes the corpus and downstream RAG.

## 1. Corpus scope and ownership

`config/nhs_sources.json` is the source-of-truth allowlist. It can be regenerated from the
NHS Symptoms A-to-Z index. Every displayed medical or everyday term is retained, while links
that resolve to the same guide URL are grouped into one source.

The manifest is tracked in Git. Parsed documents are written to `data/nhs/`, which is ignored.
The local snapshot checked on 7 September 2026 contains:

- 205 A-to-Z index entries;
- 138 unique guide JSON files after URL deduplication;
- 1,199 parsed sections and 1,221 derived retrieval chunks; and
- original fetch timestamps from 6 September 2026.

Counts are observations, not fixed acceptance values. They change when the manifest, upstream pages, or parser changes.

## 2. Source policy

An allowed requested or redirected URL must:

- use HTTPS;
- have the exact host `www.nhs.uk`;
- have a path beginning with `/symptoms/`, `/conditions/`, `/mental-health/`, or `/pregnancy/`;
- contain no username, password, or explicit port; and
- be selected by the tracked, index-derived manifest for normal ingestion. Redirect and
  canonical destinations are path-validated but need not separately appear in the manifest.

The fetcher is sequential and manifest-only. It does not recursively crawl page links.

## 3. Ingestion contract

The command is:

```bash
uv run python -m cronjobs.nhs_dataset.refresh --contact "mailto:you@example.com"
```

Supported options are `--contact`, `--delay`, `--limit`, `--force`, `--manifest-path`,
`--raw-dir`, and `--corpus-dir`.

To rediscover the full A-to-Z index, refresh the corpus, and create a Hugging Face-compatible
dataset repository in one run:

```bash
uv run python -m cronjobs.nhs_dataset --contact "mailto:you@example.com"
```

Successful HTML responses and provenance metadata are archived under `data/raw/nhs/`. Reparse
that archive and rebuild the Hugging Face export without network access using:

```bash
uv run python -m cronjobs.nhs_dataset --from-raw
```

For each run, ingestion must:

1. Load and validate every source before fetching.
2. Fetch `https://www.nhs.uk/robots.txt` and check each URL for the identifying user agent.
3. Use `GuidePostHealthRAG/0.1 (+<contact>)` as its user agent.
4. Wait 1 second between pages by default.
5. Use a 30-second timeout with a 10-second connection timeout.
6. Attempt a request at most 3 times, with exponential delay for request or validation failures.
7. Respect `Retry-After` for `429` responses, capped at 30 seconds.
8. Validate every redirect and the final URL after HTTPX has followed redirects. This does
   not prevent an out-of-scope redirect request from being sent.
9. Send `If-None-Match` and `If-Modified-Since` when prior metadata exists, unless `--force` is used.
10. Treat `304` as unchanged.
11. Gzip the successful raw HTML response and atomically retain response provenance metadata.
12. Parse the response text and atomically replace the parsed destination through a `.json.tmp`
    file. Raw body, raw metadata and parsed JSON are not replaced as one transaction.
13. Isolate failures by source, preserve any prior valid destination, continue the run, and exit non-zero when any source failed.

## 4. Parsed guide schema

Each `GuideDocument` stores:

- requested and canonical URLs;
- title and optional description;
- fetch timestamp;
- upstream `dateModified`, page-last-reviewed, and next-review-due values when present;
- HTTP `ETag` and `Last-Modified` metadata when present;
- SHA-256 over stable parsed section content;
- parser version and the OGL v3.0 licence label; and
- ordered sections with heading, text, and urgency classification.

The parser retains `h1`–`h3`, paragraphs, list items, and definition entries inside
exactly one `main#maincontent`; the document must have exactly one main element. Missing or
ambiguous regions raise an upstream-schema error in both guide and index parsing, with no
fallback. All 138 archived guides match this contract. It strips scripts, styles, SVG, forms,
navigation, pictures, whole figures, images, video, audio, iframes, `noscript`, canvas, objects
and embeds. It removes duplicate lines within each section, sections shorter than 20
characters, and sections headed `video:` or `audio:`. It does not deduplicate whole sections.

Raw HTML is retained as compressed local archives with provenance metadata; media binaries
are not downloaded. Removing figures also removes useful captions and credits. Tables are
not structurally extracted: selected descendants can survive while headers, cell boundaries
and row relationships are lost. See the detailed workflow for measured omissions and proposed
review decisions; these losses are not corrected merely by labeling the result as an adaptation.

## 5. Urgency labelling

The parser assigns one of `general`, `routine`, `urgent`, or `emergency` using NHS care-card
CSS classes and the active heading. Section aggregation ranks emergency above urgent, routine
and general. Within an individual rule check, however, routine phrases are checked before
urgent phrases; overlapping indicators can therefore yield a routine candidate. This is an
open review issue described in the detailed workflow.

This is a structural heuristic, not a clinically validated classifier. It must preserve the original text and must be evaluated whenever NHS markup or parser rules change.

## 6. Chunking and identifiers

- Sections are split into windows of at most 180 words.
- Windows overlap by 28 words, producing a stride of 152 words.
- A document ID is the first 20 hexadecimal characters of SHA-256 over the canonical URL.
- A chunk ID is deterministic UUIDv5 over canonical URL, section index, heading, chunk index, and the chunk text hash.
- Title, heading, canonical URL, fetch time, and section urgency are copied to every chunk.

Changing canonical URLs, section order, headings, window positions, or text changes the affected chunk IDs.

## 7. Embedding and index build

`SentenceTransformerEncoder` lazily loads `sentence-transformers/all-MiniLM-L6-v2`. It embeds the concatenation of title, heading, and chunk text, requests normalised vectors, and reports the model-provided dimension.

`RagService.index_corpus()`:

1. Reads sorted `data/nhs/*.json` files.
2. Skips files that do not validate as `GuideDocument`.
3. Fails readiness when no valid documents remain.
4. Chunks every valid document and embeds all chunk texts.
5. Deletes and recreates the named standalone Qdrant collection.
6. Uses cosine distance and the encoder-reported dimension.
7. Upserts serialized chunk payloads in batches of 128 with `wait=True`.
8. Verifies the stored point count and marks the process ready only after the complete build succeeds.

The collection persists in a Docker named volume. Its metadata records the schema version, corpus hash, embedding model, vector size, and chunk count so API startup can reject missing or stale data. There is no incremental update or atomic blue/green promotion yet.

## 8. Retrieval algorithm

Given a query, the current algorithm:

1. Creates one normalised query embedding.
2. Requests the top 6 cosine matches by default.
3. Takes the documents represented by the first 3 matches.
4. Appends unseen chunks labelled `urgent` or `emergency` from those documents.
5. Truncates the combined list to 9 evidence chunks by default.

The added safety chunks have the default score `0.0`; they were not independently ranked by similarity. The final cap can still exclude a safety chunk when many candidates exist.

The implementation is dense-only. It has no BM25/keyword search, reranker, metadata filter, spell correction, query expansion, entity extraction, or cross-guide clinical reasoning.

## 9. Grounding and citation selection

- The agent receives evidence ID, title, heading, urgency, and text. It does not receive URLs.
- Every generated next step and warning sign must contain at least one evidence ID from the current bundle.
- Citations are restricted to referenced chunks when references exist, deduplicated by URL plus heading, and capped at 6.
- Fallback actions use at most 3 nonurgent extracts and at most 3 urgent/emergency extracts.
- Fallback extracts are capped at 360 characters; citation excerpts are capped at 220 characters.

Evidence-ID validity proves only that a referenced chunk was retrieved. It does not prove that a statement is entailed by the chunk. The generated summary, urgency label, and follow-up question currently have no evidence-ID requirement.

## 10. Content lifecycle requirements

The following are required before a public pilot:

| ID | Requirement | Status |
| --- | --- | --- |
| CR-101 | Define a refresh service level and block or clearly degrade answers when content is stale. | Required |
| CR-102 | Schedule ingestion, alert on failures and upstream structural changes, and trigger controlled re-indexing. | Required |
| CR-103 | Review source diffs, especially urgency changes, before promoting a corpus version. | Required |
| CR-104 | Assign signed corpus, parser, embedding, and index versions with reproducible hashes and rollback. | Required |
| CR-105 | Remove orphaned JSON when a manifest source is withdrawn; the current glob index would otherwise retain it. | Required |
| CR-106 | Revalidate canonical and citation URLs during parse, index, and response construction. | Required |
| CR-107 | Pin and record the exact embedding model revision and evaluate it against a clinically reviewed query set. | Required |
| CR-108 | Add Qdrant authentication, encryption, backup/restore, and controlled index promotion. | Required for production |
| CR-109 | Define a page-level takedown and licence-exclusion process. | Required |

## 11. NHS content and attribution

The parser removes media and interactive elements and rejects pages marked as registered medical devices. These structural checks reduce but do not eliminate licensing risk. Requested and canonical URLs must stay within the four permitted guidance paths; excluded campaign paths are rejected.

The parser changes context and omits tables; records and answers are treated as adaptations with generic OGL attribution. Original-page links identify provenance, not authorship of the adaptation. The UI displays copy dates, licence links and independent/no-endorsement wording. The export carries these disclosures per record and in `NOTICE.md`. A page-level rights review and freshness policy remain required. Gitignore is a source-control choice, not a licence control. See the [7 September 2026 audit](nhs-dataset-compliance.md).

Primary references:

- [NHS website terms and conditions](https://www.nhs.uk/our-policies/terms-and-conditions/)
- [NHS content not licensed for re-use](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/)
- [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)

## 12. Separate Mayo collection

The Mayo Symptom Checker collection has its own [usage and compliance review](mayo-dataset-compliance.md)
and [per-source inventory](mayo-content-inventory.json). The NHS/OGL rules above do not
license Mayo data. Clearance for acquisition, retention, transformations and AI use remains
unresolved, including local experiments. The shared [raw archive workflow](guide-data-workflow.md)
does not combine content rights or authorize Mayo retrieval integration.
