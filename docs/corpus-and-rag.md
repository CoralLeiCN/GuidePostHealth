# Corpus and RAG specification

## 1. Corpus scope and ownership

`config/nhs_sources.json` is the source-of-truth allowlist. It currently contains 25 common symptom and condition guides discovered from the NHS Symptoms A–Z area.

The manifest is tracked in Git. Parsed documents are written to `data/nhs/`, which is ignored. The local snapshot checked on 31 August 2026 contains:

- 25 guide JSON files;
- 205 sections;
- 207 chunks after section-aware chunking;
- fetch timestamps from 30 August 2026.

Counts are observations, not fixed acceptance values. They change when the manifest, upstream pages, or parser changes.

## 2. Source policy

An allowed requested or redirected URL must:

- use HTTPS;
- have the exact host `www.nhs.uk`;
- have a path beginning with `/symptoms/` or `/conditions/`;
- contain no username, password, or explicit port; and
- appear in the manually curated manifest for normal ingestion.

The fetcher is sequential and manifest-only. It does not recursively crawl page links.

## 3. Ingestion contract

The command is:

```bash
uv run python -m nhs_rag.ingestion.cli --contact "mailto:you@example.com"
```

Supported options are `--contact`, `--delay`, `--limit`, and `--force`.

For each run, ingestion must:

1. Load and validate every source before fetching.
2. Fetch `https://www.nhs.uk/robots.txt` and check each URL for the identifying user agent.
3. Use `GuidePostHealthRAG/0.1 (+<contact>)` as its user agent.
4. Wait 1 second between pages by default.
5. Use a 30-second timeout with a 10-second connection timeout.
6. Attempt a request at most 3 times, with exponential delay for request or validation failures.
7. Respect `Retry-After` for `429` responses, capped at 30 seconds.
8. Validate every redirect and the final URL with the same exact-host/path rule.
9. Send `If-None-Match` and `If-Modified-Since` when prior metadata exists, unless `--force` is used.
10. Treat `304` as unchanged.
11. Parse successful HTML and atomically replace the destination through a `.json.tmp` file.
12. Isolate failures by source, preserve any prior valid destination, continue the run, and exit non-zero when any source failed.

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

The parser retains text from headings, paragraphs, list items, and definition lists inside `main#maincontent` or the first `main`. It strips scripts, styles, SVG, forms, navigation, pictures, figures, video, audio, iframes, and `noscript` content. Duplicate lines and sections shorter than 20 characters are removed.

Raw HTML and media are not retained.

## 5. Urgency labelling

The parser assigns one of `general`, `routine`, `urgent`, or `emergency` using NHS care-card CSS classes and phrases found in headings or nearby elements. Emergency has the highest rank, then urgent, routine, and general.

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

The parser deliberately excludes branding assets, media, forms, and interactive content. That reduces but does not eliminate licensing risk.

NHS terms require correct attribution and include content that is not available under the standard reuse terms. The service must retain original source links, copied-as-at information, an OGL statement, and independent/no-endorsement wording. A page-level legal review and freshness policy remain required. Gitignore is a source-control choice, not a licence control.

Primary references:

- [NHS website terms and conditions](https://www.nhs.uk/our-policies/terms-and-conditions/)
- [NHS content not licensed for re-use](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/)
- [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
