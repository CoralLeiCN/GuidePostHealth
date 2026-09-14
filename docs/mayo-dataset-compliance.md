# Mayo dataset usage and compliance review

Reviewed **8 September 2026** against the local working tree, existing Mayo artifacts and
official policies linked below. **Status: usage permission unresolved; compliance is not
certified.** This records engineering evidence and operating requirements, not legal approval.
No written grant covering this corpus was found in the reviewed project documentation or
artifact metadata. This does not establish whether the operator holds permission elsewhere.

## Intended use and present decision

GuidePost Health is a local project for LLM testing and learning RAG with fictional questions.
The Mayo collection contains public Symptom Checker pages, not patient records. Its intended
local, educational use does **not** establish a right to acquire, transform or reuse the pages.
Mayo material does not inherit the NHS Open Government Licence or the software's Apache-2.0
licence. The `licence` field in the Mayo manifest and records is a copyright notice, not a grant.

**Operating requirement pending clearance:** do not run further automated Mayo collection,
reprocessing, embedding, model use or transfers until the operator records a written permission
covering the activity or a qualified legal determination of another applicable basis. Existing
copies require a retention/removal decision; their presence is not approval for continued use.
This is a documented requirement, **not an implemented runtime block**. The existing commands
remain executable. This review neither deletes nor refreshes the corpus.

## Official policy evidence

These are the policies retrieved on the review date, not proof of their wording at the earlier
acquisition times. Recheck them when the intended use or permission changes.

| Source | Relevant published position |
| --- | --- |
| [Website terms](https://www.mayoclinic.org/about-this-site/terms-conditions-use-policy), displayed update 12 April 2024; **Acceptable use** and **Intellectual property** | Prohibit automated access/copying and bypassing access restrictions. The personal, noncommercial exception permits one unmodified copy on one computer with notices/disclaimers and no suggested association; other copying and transmission require prior written consent. |
| [Reprint permissions](https://www.mayoclinic.org/about-this-site/reprint-permissions), **Eligibility**, **Guidelines** and **Exclusions** | Limited print reuse has completeness, attribution and copyright conditions. Electronic/online reuse is excluded. Interactive tools and tables, specifically Symptom Checker, are excluded content. Exceptions require preapproval. The eligible short-excerpt provision does not clear this excluded collection. |
| [Terms for licensed content](https://www.mayoclinic.org/about-this-site/terms-use-licensed-content), opening agreement and final copyright paragraph | A separate consumer-facing agreement still limits reuse and requires permission from applicable rights holders for other uses. Its title does not confer a licence to this project. It also disclaims medical use, endorsement and guarantees of accuracy or timeliness. |
| [Linking guidelines](https://www.mayoclinic.org/about-this-site/guidelines-sites-linking-to-mayo-clinic), **Links to interior pages** and **General guidelines** | Allow ordinary text links using the prescribed topic naming; prohibit framing/reposting and association claims. Links should remain valid and should not use Mayo logos or images. Linking does not authorize copying the target content. |
| [Mayo Global Business Solutions content licensing](https://gbs.mayoclinic.org/licensable-content/) | Provides a licensing/contact route and content platform. Availability of a licensing program is not an agreement, nor evidence that these exact Symptom Checker pages or AI uses are offered. Confirm scope with Mayo. |

The distinctions below are this project's application of those policies to its artifacts.
They are not quotations of an AI-specific policy or a determination of fair use, fair dealing
or text-and-data-mining exceptions. Any reliance on an exception needs jurisdiction- and
activity-specific review, including the access terms.

## What exists locally

The [manifest](../config/mayo_sources.json) lists **45 related-factor pages: 28 adult and 17
child**. The [per-source inventory](mayo-content-inventory.json) records their identities,
original timestamps, hashes and pending review fields without copying medical passages.

| Artifact | Observed snapshot and limits |
| --- | --- |
| `data/raw/mayo/<slug>.html.gz` and `.metadata.json` | 45 full DOM archives, captured 7 September 2026, 22:52:23.977–22:52:54.142 UTC. All are labelled `browser_dom` / `full_document`; decompressed SHA-256 and byte lengths match their metadata. DOM serialization is not the original HTTP body. |
| `data/raw/mayo/browser-captures/` | Inputs used by the offline importer. They are also copied content and need the same retention and permission review. |
| `data/mayo/raw/` and `data/mayo/documents/` | Earlier snapshots and 45 parsed records, captured 7 September 2026, 01:54:05.855–01:57:18.761 UTC. Parsed records use `mayo-1` / `browser_snapshot`, with 184 factor groups and 1,140 options. These predate the full archives; there is no established replay lineage from the new archives. |
| `data/mayo/dataset.jsonl` and `report.json` | Earlier local export/report. A successful build report describes processing, not reuse clearance. |

All these locations are Git-ignored; no files under `data/raw/mayo/` or `data/mayo/` are tracked.
Gitignore does not control backups, file copies or provider submissions. No remote storage,
external model history or deployed application was audited for earlier Mayo copies.

## Usage requirements

| Activity | Requirement for this project |
| --- | --- |
| HTTP download or browser automation | Resolve permission for automated acquisition before another run. A successful response, robots allow rule, rate limit or contact user agent cannot supply that permission. Do not use browser capture, alternate identities or proxies to work around a refusal. |
| Existing raw copies and offline import | Record whether the existing acquisitions and continued storage are covered, including duplicate captures and backups. Offline processing does not cure an acquisition or reuse restriction. |
| Parsing, normalization, isolated excerpts and translation | Obtain scope covering the actual transformations. The parser restructures factor labels and extracts advice while omitting page context; these are not unchanged copies. Removing images does not establish rights to the remaining text or interactive structure. |
| Chunking, embeddings, vector storage and local RAG | Include these operations and retained derived artifacts explicitly in the clearance decision. This review found no grant for them; local execution or numeric output does not itself resolve content rights. |
| Model prompts, evaluation, training or fine-tuning | Resolve each intended use separately, including passage transmission, provider retention/training, output reuse and any model/embedding distribution. RAG inference is distinct from model training; neither is cleared by this review. A provider contract cannot supply missing Mayo rights. |
| Git, Hugging Face, shared drives, APIs and app displays | Do not distribute the Mayo corpus or derived extracts under NHS/OGL metadata. Private sharing is still a transfer needing a covered audience and destination. Any future Mayo exporter must carry its own terms, permission scope, provenance and notices. |
| Ordinary source links | Follow Mayo's linking guidance. Use a label such as `MayoClinic.org [topic] Information`, with the actual topic substituted, without embedding the page or implying a relationship. |
| Commercial, public or clinical use | Outside this project's current scope. Content permission and separate product/privacy/clinical reviews would be needed for a scope change. A citation or disclaimer is not clinical validation. |

## Existing controls and gaps

- The [raw downloader](../cronjobs/mayo_dataset/downloader.py) validates manifest URLs,
  checks robots rules for HTTP acquisition, fetches sequentially, rejects redirects and
  records failures. It does **not** check site terms, permission scope or a rights decision.
- Browser import checks URL identity, timestamp and full-document structure. It makes no
  request to verify robots or terms and records no capture-time access authorization.
  Earlier workflow notes report that direct HTTP returned 403 before browser capture.
  That history is an **unresolved acquisition issue**, not a recommended fallback.
- The [shared archive reader](../cronjobs/raw_archive.py) checks hashes and lengths. Those
  checks establish consistency of local files, not authenticity, authorization or freshness.
  Raw HTML retains navigation, branding, scripts and other embedded markup; linked media
  bytes are not bundled. Rights and privacy review must include the retained markup.
- The [legacy parser](../backend/nhs_rag/ingestion/mayo/parser.py) retains source links,
  copy dates, population, factor identifiers and a copyright notice. It does not preserve
  every source disclaimer or page context. All 45 parsed records lack a terms URL,
  permission reference and rights-review status; the new inventory supplies an audit record
  but does not retrofit those fields or make the records transferable.
- Cause mappings are `not_collected` and urgency classification is `not_performed`.
  Adult/child scope and original advice must remain identifiable in any authorized adaptation.
  The material does not reconstruct the complete interactive checker or establish safe UK
  triage. Do not infer causes from factor IDs or silently convert US advice to NHS routes.
- The default app uses NHS retrieval. The new Mayo raw job stops before parsing/export/indexing;
  a separate legacy local exporter exists. There is no automatic Mayo rights gate at any
  stage, no approved refresh interval and no exercised Mayo takedown process.

## Attribution, privacy and lifecycle

For an authorized use, retain the original publisher, URL, acquisition date, source/version
hashes, applicable terms and the actual permission reference. Carry the required copyright
notice and source disclaimers; label GuidePost transformations and generated answers clearly.
The [repository notice](../NOTICE.md#mayo-clinic-content) identifies the rights holder and
unresolved status. Notices document provenance; they do not grant reuse rights.

Use fictional test inputs. Public health information and real users' symptom descriptions
are different data categories. Review full DOM captures for identifiers, session-related
values and third-party material before any authorized transfer. Do not extend collection to
patient portals, accounts or community posts. If real user information is later proposed,
resolve operator/provider roles, legal basis, retention, training settings, access, transfers,
deletion and incident handling under the separate [privacy governance requirements](safety-and-governance.md#8-privacy-and-data-governance).
No claim of GDPR or HIPAA compliance follows from using public pages or local files.

Any agreed retention and refresh rules must cover source captures, fragments, parsed JSON,
JSONL, chunks, embeddings, indexes, prompt/output caches, backups and authorized remote copies.
On expiry, withdrawal, source removal or a rights complaint: stop affected acquisition/use;
identify every derivative by source and hash; restrict or remove copies as required by the
agreement and applicable obligations; invalidate dependent indexes/exports; and record the
action and verification. An offline reparse must retain the original acquisition date.
Do not invent an NHS-style refresh interval for Mayo.

## Evidence needed to close the open review

1. **Permission/basis and scope:** record a grant/reference or reviewed legal basis covering
   these exact pages, existing acquisition/storage, automated access, intended transformations,
   AI operations, users/devices, providers, locations and any distribution. Record expiry,
   attribution, refresh, deletion, sublicensing and third-party exclusions. Mayo's
   [permission process](https://www.mayoclinic.org/about-this-site/reprint-permissions) and
   [licensing program](https://gbs.mayoclinic.org/licensable-content/) are contact routes;
   no request was sent during this review.
2. **Page/version decisions:** every inventory record remains `pending_permission_and_manual_review`.
   A reviewer must record their name, date, evidence, permission reference, allowed uses and
   any exclusions against the exact hashes. A raw-file checksum passing is not a rights decision.
3. **Artifact disposition and controls:** decide retention/removal of existing copies, propagate
   rights metadata before authorized downstream use, and select how permission checks should
   be enforced. The current documented hold relies on the operator; implementation remains open.
4. **Revalidation:** revisit changed pages, policies, permission expiry, new recipients and new
   uses. Keep dated decisions and check that stale artifacts cannot enter an authorized build.

These items are tracked in [BL-024](../backlog.md#mayo-acquisition-alignment). Full compliance
must not be inferred from completion of this documentation task.

## Verification of this documentation change

The inventory covers all 45 manifest URLs and verifies the raw archives' URL identity,
decompressed hashes and lengths. It also hashes the earlier parsed files, snapshots and local
export/report separately, preserving their independent lineage. All rights decisions remain
pending. Existing acquisition/processing code and data were left unchanged; no clinical
validation, corpus refresh, model submission, upload or deployment was performed.
