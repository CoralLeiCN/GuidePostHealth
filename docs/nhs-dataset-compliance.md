# NHS dataset compliance review

Reviewed 7 September 2026 against the local working tree, downloaded corpus and current
official NHS reuse terms. **Status: concrete attribution and disclosure defects corrected;
full compliance is not certified. Page-level rights clearance remains open.** This is an
engineering review, not legal approval or clinical validation. No upload or deployment was
performed. Changes already present in the working tree were retained.

## Intended use

GuidePost Health is for local LLM testing and learning RAG using fictional scenarios. It is
not designed or intended for any public use, personal health guidance or clinical use.
References below to public-use privacy and clinical reviews describe a separate change of
scope, not a planned release. Content-licence obligations still apply to local experiments.

## What was reviewed

- `config/nhs_sources.json`: 205 index entries, deduplicated to 138 guides from the NHS
  Symptoms A to Z index. This is a derived public website corpus, not patient-record data.
- All 138 local parsed documents and corresponding compressed HTML files. Original fetches
  span 6 September 2026, 15:51:19–15:53:43 UTC; offline reparsing preserves those dates.
- 1,199 parsed sections, JSONL exports, dataset-card generator, Hub transfer allowlist,
  parser/downloader, API notices, reference links and frontend disclosures.
- [Per-page inventory](nhs-content-inventory.json) records original/canonical URLs, fetch
  times, content and raw-file hashes, parser version and outstanding review status. It is
  an automated inventory, not a claim that a person has cleared every passage.

## Governing sources

1. [NHS website terms, especially 3.3–3.11](https://www.nhs.uk/our-policies/terms-and-conditions/)
   permit eligible reuse subject to the NHS terms and OGL, distinguish unchanged copies from
   adaptations, restrict endorsement and charging, and require lawful personal-data processing.
2. [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
   permits copying, adaptation and commercial reuse with attribution. It does not grant rights
   to third-party intellectual property, personal data or official endorsement.
3. [NHS exclusions](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/)
   identify excluded campaign sites and media, state that the list is incomplete, and refer
   API/widget users to separate refresh terms. This project uses HTML, not an NHS API/widget.

The live text of NHS section 3.6(b) appears to omit part of its opening condition. Its
instruction on generic attribution for adapted content is present. We apply that instruction
conservatively and do not represent our extracts as unchanged NHS publications. Obtain NHS
clarification or legal advice if a different attribution approach is needed.

## Findings and corrections

| Finding | Evidence and resulting action |
| --- | --- |
| Adaptations labelled as direct NHS information | The exporter previously attributed every row as NHS information. Parser output removes layout, context and links, and assigns heuristic urgency. Both guide and section rows now carry generic OGL attribution, an explicit adaptation notice, licence/terms URLs and separate original-publisher provenance. The card states independence and lack of clinical approval. |
| Copy-date disclosure was misleading or inaccessible | The card used the newest fetch date as a date for the entire corpus; it now shows the fetch range and retains individual timestamps. UI dates were tooltips; they are now visible. The emergency link previously invented a fetch time on every request; it now has no fetch date and is labelled as a service link. |
| Unsupported freshness and authorship claims | Removed the UI's “current” claim and “NHS-guided answer” label. API responses distinguish GuidePost adaptations from original reference pages and provide licence information. The fixed emergency response remains labelled as a fixed safety message. |
| Incomplete licence packaging | Added a repository notice distinguishing Apache-2.0 software from content rights. Generated datasets contain `NOTICE.md`, which Hub transfer requires and includes. Raw HTML is excluded from the transfer allowlist. |
| Incomplete exclusion controls | Source/canonical paths are validated during parsing and export, including traversal attempts into excluded campaigns. Parser version 2 removes additional embedded-media elements and rejects pages containing a registered-medical-device label. These are structural safeguards, not comprehensive rights detection. |
| Misleading chat privacy copy | Replaced the browser-only implication with disclosure of transmission to the service and, when enabled, its configured AI provider. This does not replace the operator-specific privacy notice. |

For an unchanged copy, NHS section 3.6(a) requires instance-level NHS attribution and original
page links, plus a prominent licence statement. It offers a disclosed-copy-date route or the
specified refresh route (normally at least weekly); daily refresh is recommended. Our
adaptations instead use the generic OGL statement. Keeping a date is not a clinical freshness
guarantee. Source links are labelled as original reference material, not NHS authorship or
approval of an AI response.

## Remaining conditions before distribution or public use

1. **Clear rights per page and version.** All 138 inventory entries remain pending manual
   review. Check retained text and metadata for third-party credits, special terms, personal
   data, restricted content and medical-device material. The 26 pages containing media had
   media removed; sampled third-party credits on rash and worm pages were inside removed
   figures and absent from parsed output. That does not prove every retained passage is
   eligible. Record reviewer, decision, date, evidence and content hash. Remove uncertain
   passages/pages or obtain permission; never assume an NHS domain makes all content OGL.
2. **Resolve content integrity before health use.** Tables appear on 44 original pages and
   are omitted or lose their relationships in this parser. Short-section filtering,
   deduplication, lost link targets and excerpt truncation can also remove qualifications.
   Adaptation labels disclose the limitation; they do not make incomplete medical guidance
   safe. These are useful defects to study in local RAG experiments. A separately proposed
   public or clinical application would need extraction and clinical-safety evaluation.
3. **Operate refresh and takedown controls.** A refresh command exists, but no active schedule
   or removal process was verified. Review source changes and exclusions, reparse, rebuild
   exports and reindex Qdrant as one controlled release. On withdrawal, remove the affected
   local and hosted records and derived indexes. An offline reparse does not refresh content.
4. **Finish privacy governance before real health-data collection.** The backend forwards the
   question, recent history and passages to its configured model provider when enabled.
   Identify the actual operator/provider, purposes, lawful basis, retention, transfers,
   user rights and contact route, and complete the needed agreements and privacy assessment.
   No processor identity or retention promise was invented in this review.
5. **Respect downstream use restrictions.** Do not imply NHS endorsement, reuse NHS branding
   or medical devices, or levy a separate charge for NHS content. OGL reuse does not establish
   clinical suitability or regulatory approval. Keep copied dates, provenance and adaptation
   notices with downstream displays, API consumers and dataset copies.

The export metadata explicitly says `pending_page_level_review`. The Hub helper validates
packaging but **does not enforce manual rights sign-off**; its existence is not permission to
publish. An operator must resolve the review before using it to distribute content. No
remote dataset or deployed site was inspected or changed, so earlier remote copies, if any,
still need a separate review and authorised update.

## Verification

All 138 documents were reparsed offline with parser version 2 and the local dataset was
regenerated: 1,199 sections, no failures, original fetch timestamps preserved. The Python
suite includes regression checks for excluded canonical destinations, embedded-media
fallbacks, medical-device markers, mixed copy dates, notices in Hub transfers and truthful
emergency-link provenance. All 32 tests passed. Python lint and strict typing, frontend lint,
TypeScript checks and the local production build passed. Existing Qdrant collections were
not rebuilt by this audit.
