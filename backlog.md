# Project backlog

Last updated: 7 September 2026.

This is the central tracker for known unfinished work. Technical specifications describe the
behavior and evidence; this file owns work status. Existing requirement IDs are retained as
references so the same issue is not silently tracked twice. Add newly discovered work here,
link its detailed evidence, and update both this tracker and the affected spec when it closes.

Scope: local LLM testing and RAG learning with fictional questions. Listing an item does not
authorize implementation, media acquisition, uploading, deployment or a public/clinical product.
All unfinished items currently have **no assigned owner or target date**. Assign those when
work is selected; do not infer priority from ID order.

| Status | Meaning |
| --- | --- |
| Proposed | Known work awaiting prioritization; not started. |
| Deferred | Explicitly postponed; revisit before implementation. |
| In progress | Selected and actively being implemented. |
| Done | Acceptance criteria met; evidence linked. |
| Conditional / out of scope | Relevant only if the user separately changes the project scope. |

## Dataset and extraction

| ID | Status | Work and rationale | Acceptance criteria | References |
| --- | --- | --- | --- | --- |
| BL-001 | Done | Require unambiguous `main#maincontent` in guide and index parsing; reject template drift without a generic-main fallback. | Exactly one main with the expected ID; explicit error identifies URL and observed counts; missing/renamed/wrong-tag/duplicate/extra-main tests; a failed offline parse prevents export and preserves prior parsed output. | Workflow D-01; [content.py](cronjobs/nhs_dataset/content.py); [tests](tests/test_nhs_dataset_job.py). |
| BL-002 | **Deferred** | Review useful information lost through multimedia filtering: images, captions, alt text, video/audio and transcripts. User deferred this review on 7 September 2026. Current removal behavior stays in place. | Inventory media references, surrounding headings, captions/alt/transcripts and rights/credits; assess what text stands alone; decide what can be retained and how to flag visual-dependent passages; record decisions and tests before changing extraction. No automatic download, transcription or generated image descriptions. | Workflow D-02, [multimedia analysis](docs/nhs-dataset-workflow.md#6-removal-and-the-multimedia-tradeoff). Evidence: 62 captions on seven pages; 17 video elements on 17 pages. |
| BL-003 | Proposed | Preserve table relationships instead of flattening/omitting cells and headers. | Review all 52 tables on 44 archived pages; represent headers, rows and cells; test plain/paragraph cells, spans and nested lists; compare source and parsed context. | Workflow D-03. |
| BL-004 | Proposed | Preserve heading/expander context and meaningful short or repeated text. | Fixtures for h4–h6, details/summary, nested lists, short instructions and repeated qualifiers; decide deduplication and section-length rules; report discarded text and changed output. | Workflow D-04. |
| BL-005 | Proposed | Audit urgency heuristics, especially routine checks preceding urgent checks within one candidate. | Tests for overlapping indicators; record the rule responsible for each label; review disagreements; retain an explicit unvalidated-heuristic label. | Workflow D-05; CR-103; SG-005. |
| BL-006 | Proposed | Record complete build provenance and extraction losses. | Build ID, source/parsed/artifact hashes, selector and parser/dependency versions, original fetch and later verification timestamps, removed-element counts; propagate needed provenance to section records; normalize timestamp comparisons; validate metadata/schema consistency. | Workflow D-06; CR-104. |
| BL-007 | Proposed | Make a multi-file build coherent and complete. | Detect slug collisions and empty manifests; reject mixed/unsupported parser versions and bad hashes; stage/promote raw/parsed/export artifacts coherently; recover interrupted writes; handle orphaned documents without indexing withdrawn sources; reject or report invalid inputs instead of silently skipping them. | Workflow D-07; CR-105; workflow sections 1, 4, 8–9. |
| BL-008 | Proposed | Strengthen fetch boundaries and historical discovery replay. | Validate redirects before requests, assess robots rules per destination, enforce size/media-type limits, support HTTP-date Retry-After, archive discovery inputs, resolve relative canonicals against the final page URL; test failures without contacting unintended hosts. | Workflow sections 3–5; CR-106. |
| BL-009 | Proposed | Define corpus refresh, source-diff review, exclusions and takedown lifecycle for reproducible experiments. | Document refresh/verification policy, record failures and source changes, ensure parser updates reparse cached bodies, invalidate affected derived outputs/indexes, and document rollback/removal. Any schedule is a separately selected action. | CR-101–103, CR-109; compliance review. |
| BL-010 | Proposed | Complete page/version rights review before any distribution. | Review retained passages and metadata against applicable exclusions; record reviewer, date, evidence and hashes; remove or obtain permission for uncertain material. Decide whether transfer should enforce sign-off. | [Compliance review](docs/nhs-dataset-compliance.md), [rights inventory](docs/nhs-content-inventory.json); overlaps with BL-002 only for media rights. |
| BL-011 | Proposed | Validate exported bundles and Hub transfers more fully. | Validate actual JSONL rows/counts/checksums and notices; version schemas and loader metadata; verify remote visibility when relevant; handle obsolete remote files explicitly; define any export-to-application import path. Do not treat a successful transfer as content approval. | Workflow section 8. |

## Retrieval, answers and local operation

| ID | Status | Work and rationale | Acceptance criteria | References |
| --- | --- | --- | --- | --- |
| BL-012 | Proposed | Evaluate chunking, embedding and retrieval quality with reproducible fictional scenarios. | Pin exact model revision, measure token-limit truncation and context loss, establish retrieval/entailment/citation metrics, test urgent-evidence recall and cap behavior. Hybrid search or reranking remains an experiment to justify, not an automatic feature addition. | CR-107; SG-004, SG-006; workflow section 9. |
| BL-013 | Proposed | Improve answer grounding and urgency consistency. | Assess summary, help level and follow-up grounding; compare claims to passages instead of only validating IDs; evaluate preserving evidence qualifiers/urgency; test unsupported claims and fallback truncation. | SG-003–005; API/agent and safety specs. |
| BL-014 | Proposed | Clarify and test fixed emergency handling during failures and complex language. | Specify local demo behavior with an unavailable index, negation, historical/quoted statements and conversation context; test expected routes. This does not convert the phrase rule into validated triage. | SG-001–002. |
| BL-015 | Proposed | Report failures and resource limits in local experiments. | Distinguish provider/schema/timeouts and fallback causes; avoid recording sensitive message bodies; evaluate whole-request timeout/cancellation, concurrency/backpressure and bounded history. Keep the single-worker limitation documented. | SG-008; operations sections 5–6. |
| BL-016 | Proposed | Validate corpus and citation integrity at every consumer boundary. | Revalidate allowed URLs when indexing/responding, reject malformed or stale payloads, and associate displayed provenance with the correct artifact. Parse-time URL checks already exist. | CR-106; SG-010. |
| BL-017 | Proposed | Evaluate UI and end-to-end local behavior. | Fictional-scenario tests for errors, fallback, source links, copy dates, keyboard access and responsive layout; assess useful live corpus/readiness state. No personal-health use claims. | PR-103, PR-105; operations sections 5–6. |

## Conditional items outside the current project scope

These preserve the previously documented governance and production items so they are not
lost. They are not planned releases or prerequisites for documenting local experiments.

| ID | Status | Work / condition | Completion evidence if scope changes | Existing references |
| --- | --- | --- | --- | --- |
| BL-018 | Conditional / out of scope | Public/clinical purpose, users, populations, claims, governance and regulation. | Separately approved scope, accountable owners, applicability decisions, relevant safety case and hazard log, clinical evaluation and change/incident processes. | PR-101; CG-101–106; operations milestones 1 and 4 and open decisions. |
| BL-019 | Conditional / out of scope | Real health-data processing and conversation persistence. | Actual operator/provider roles, lawful basis, assessment and agreements, retention/region/rights procedures, privacy notice and evidence of logging/minimization controls. Existing transmission disclosure is only a partial fix. | PR-104; SG-009; PG-101–107; operations open decisions. |
| BL-020 | Conditional / out of scope | Production hosting, security, availability and recovery. | Approved hosting/audience, authentication/abuse controls, TLS/secrets/network isolation, Qdrant security/backup/restore, signed artifact promotion, monitoring, load/security tests, rollback and recovery exercises. No deployment is authorized by this item. | CR-104, CR-108; operations milestones 2–4 and open decisions. |
| BL-021 | Conditional / out of scope | Public accessibility, feedback/incident routes and localization. | Audience-appropriate accessibility/health-literacy evaluation; governed feedback without unnecessary health-data collection; explicitly selected languages and reviewed translation process. | PR-105–107. |

## Completed corrections and migration notes

- **BL-001 / D-01:** implemented with parser version `3`. Schema errors are caught by the
  existing per-page job reporter, printed with their source, and cause a nonzero run result.
  Discovery errors stop manifest replacement. This validates the main-region contract, not
  every possible upstream structural change.
  Verification on 7 September 2026: all 45 Python tests, lint and strict typing passed; all
  138 archived guides reparsed with identical text/provenance and only the parser version changed.
- **SG-007:** the invented fetch timestamp was already removed; fixed emergency links now
  have `fetched_at = null` and are displayed as official-service links without a local copy.
  A richer versioned service-source record, if needed, belongs with BL-016.
- **PR-102–104:** misleading current-content/count/browser-only claims were already corrected.
  Remaining freshness, live-state and operator-specific privacy work is tracked above.
- Multimedia handling is unchanged. **BL-002 remains deferred** until the user resumes it.

When closing an item, record the date, changed implementation/spec, relevant verification and
remaining limits. Do not delete an ID; retain it here or link its archived completion record.
