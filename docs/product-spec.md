# Product specification

## 1. Product statement

GuidePost Health is a research prototype that helps a person in England find and understand relevant guidance from a curated set of NHS symptom and condition guides.

The current product may summarise retrieved guidance, surface warning signs, suggest an official route such as NHS 111, and link to the original NHS pages. It must not diagnose, rule out a condition, claim that symptoms are harmless, or present generated wording as NHS-authored or clinically approved.

This statement describes the prototype boundary, not a completed medical-device “intended purpose”. A qualified regulatory determination and a formally approved intended-purpose statement are required before public use.

## 2. Users and context

### Current research users

- An adult seeking general information about their own symptoms.
- A parent or carer seeking a relevant NHS page, where the curated corpus includes appropriate guidance.
- Developers, clinicians, safety specialists, and researchers evaluating the prototype.

### Current context

- England-focused because the interface refers to NHS 111 and the source material is from `nhs.uk`.
- English language only.
- Text-only, browser-based interaction.
- Local development or controlled evaluation, not unsupervised public use.

### Excluded uses

- Diagnosis, differential diagnosis, prognosis, or reassurance that a condition is absent.
- A replacement for 999, A&E, NHS 111, a pharmacist, GP, or other clinician.
- Medication selection or dose calculation.
- Complete emergency detection or autonomous triage.
- Access decisions, treatment decisions, or a clinical record.
- Coverage of all symptoms, conditions, ages, pregnancies, comorbidities, or UK nations.

## 3. Product goals

1. Retrieve the most relevant passages from locally stored NHS guidance.
2. Preserve source urgency and important qualifiers such as age, pregnancy, and duration.
3. Turn evidence into short, understandable next-step guidance without inventing health facts.
4. Keep original NHS sources visible and server-controlled.
5. Fail safely to labelled source extracts when synthesis is unavailable or invalid.
6. Keep the answer harness replaceable so a governed production workflow can be substituted later.

## 4. Primary journey

1. The user reads the persistent 999 warning and enters a symptom description.
2. The browser sends the latest message and recent chat history to the API.
3. The API validates the request and confirms that the corpus index is ready.
4. A deterministic rule intercepts a small set of obvious emergency phrases.
5. Otherwise, the system retrieves NHS evidence and asks the constrained answer agent to produce structured guidance.
6. The server validates evidence references and returns a response mode, urgency label, summary, actions, warning signs, optional question, and NHS citations.
7. If the agent fails, the user sees labelled source extracts instead of generated personalisation.

The readiness check currently happens before the emergency rule. This is a known safety gap: when the index is unavailable, the API returns `503` rather than the fixed 999 response.

## 5. Functional requirements

### Implemented MVP requirements

| ID | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| PR-001 | Accept a plain-text user message between 2 and 2,000 characters. | Implemented | `backend/nhs_rag/models.py` |
| PR-002 | Accept at most 10 prior messages, with roles limited to `user` and `assistant`. | Implemented | `backend/nhs_rag/models.py` |
| PR-003 | Retrieve evidence from the ignored local NHS corpus using a persistent standalone vector index. | Implemented | `backend/nhs_rag/retrieval/service.py` |
| PR-004 | Add urgent or emergency sections from the most strongly matched guides to the evidence candidate list. | Implemented | `backend/nhs_rag/retrieval/service.py` |
| PR-005 | Generate only a structured response and require known evidence IDs for each generated next step and warning sign. | Implemented | `backend/nhs_rag/agent/` |
| PR-006 | Construct source titles and URLs from the server-owned corpus, never from model output. | Implemented | `backend/nhs_rag/service.py` |
| PR-007 | Return source extracts if Codex is disabled, times out, is unavailable, or produces invalid output. | Implemented | `backend/nhs_rag/service.py` |
| PR-008 | Bypass retrieval and generation for the currently recognised non-negated emergency phrases. | Implemented, limited | `backend/nhs_rag/safety/urgency.py` |
| PR-009 | Expose liveness, readiness, source inventory, and chat endpoints. | Implemented | `backend/nhs_rag/main.py` |
| PR-010 | Provide empty, loading, success, retrieval-only, emergency, and API-error interface states. | Implemented | `app/page.tsx` |
| PR-011 | Keep chat state in React memory and provide a “New chat” action. | Implemented | `app/page.tsx` |
| PR-012 | Show persistent 999, NHS 111, not-a-diagnosis, independent-project, and source-attribution copy. | Implemented | `app/page.tsx` |

### Required before a public pilot

| ID | Requirement | Status |
| --- | --- | --- |
| PR-101 | Approve a precise intended purpose, target users, age ranges, geography, contraindications, and exclusions with clinical, legal, and regulatory owners. | Required |
| PR-102 | Replace marketing phrases such as “current” and “reviewed” with defined, measurable freshness and review states. | Required |
| PR-103 | Display live corpus availability, guide count, and visible copied/reviewed dates instead of the hard-coded “25 reviewed guides” label and tooltip-only date. | Required |
| PR-104 | Make the privacy copy explain browser storage separately from API and external model processing. | Required |
| PR-105 | Complete formal accessibility, health-literacy, keyboard, screen-reader, zoom, mobile, and error-recovery testing. | Required |
| PR-106 | Add a governed feedback and safety-incident route that does not invite users to send unnecessary health data. | Required |
| PR-107 | Define supported languages and an evidence-backed translation process before adding localisation. | Required if multilingual support is planned |

## 6. Current interface contract

- The empty state offers examples for cough, headache, and a child with a high temperature.
- `Enter` sends; `Shift+Enter` inserts a newline.
- Concurrent submissions are blocked while an answer is pending.
- The UI sends at most the last 8 rendered messages. Assistant history contains the prior summary, not the full structured response. The agent prompt uses at most the last 6 history items.
- A successful response shows urgency, summary, next steps, warning signs, an optional follow-up question, source links, and the server notice.
- `retrieval_only` responses receive an additional “Source extracts” label.
- Citation links open the original page in a new tab. The copied-at date is currently available only in a hover tooltip; citation excerpts are returned by the API but not rendered.
- Error responses are displayed in an amber card. There is no retry button, streaming, cancellation, durable conversation, authentication, or feedback control.
- The layout becomes a chat-and-information two-column view on large screens and a single column on smaller screens.

## 7. MVP acceptance criteria

The local engineering MVP is accepted when all of the following hold:

- The manifest contains only explicitly curated `https://www.nhs.uk` symptom or condition URLs.
- A fresh machine can install dependencies, ingest the corpus, start both runtimes, and receive a cited response.
- The API stays unready when no valid corpus is present.
- A recognised emergency phrase returns the fixed emergency response before retrieval when the index is ready.
- An agent failure returns labelled source extracts.
- Unknown or missing evidence IDs in agent actions are rejected.
- Backend tests, lint, and type checking pass, and the frontend lints and builds.

These criteria are engineering acceptance only. They do not satisfy the public-pilot gate defined in [Safety and governance](safety-and-governance.md).
