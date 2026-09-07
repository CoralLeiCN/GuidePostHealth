# Product specification

## 1. Product statement

GuidePost Health is a local project for LLM testing and learning retrieval-augmented generation (RAG), using NHS symptom and condition guides as an example corpus. It is not designed or intended for any public use, personal health guidance or clinical use.

The current product may summarise retrieved guidance, surface warning signs, suggest an official route such as NHS 111, and link to the original NHS pages. It must not diagnose, rule out a condition, claim that symptoms are harmless, or present generated wording as NHS-authored or clinically approved.

Public and clinical applications are outside the current scope. The review requirements below are conditional on a separate decision to change that scope; they are not planned release milestones.

## 2. Users and context

### Current research users

- Developers, learners and researchers testing LLM and RAG behaviour locally.
- Evaluators using fictional scenarios, not real patient information or personal health questions.

### Current context

- England-focused because the interface refers to NHS 111 and the source material is from `nhs.uk`.
- English language only.
- Text-only, browser-based interaction.
- Local learning and technical evaluation only; no public-facing service.

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
6. Keep the answer harness replaceable to compare models and RAG approaches.

## 4. Primary journey

1. The evaluator reads the local-learning notice and enters a fictional test scenario.
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

### Conditional requirements if public use is separately proposed (out of scope)

| ID | Requirement | Status |
| --- | --- | --- |
| PR-101 | Approve a precise intended purpose, target users, age ranges, geography, contraindications, and exclusions with clinical, legal, and regulatory owners. | Required |
| PR-102 | Unsupported freshness/review claims have been removed. Define measurable freshness and review states for any separate public application. | Partly implemented; remaining work out of scope |
| PR-103 | Copy dates are visible and the stale guide-count badge is removed. Live corpus availability/count remains future work. | Partly implemented; remaining work out of scope |
| PR-104 | Transmission to the service and AI provider is disclosed. An operator-specific privacy notice would be needed for any separate public application. | Partly implemented; remaining work out of scope |
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
- Citation links open the original page in a new tab. The copied-at date is visible beneath each reference link; citation excerpts are returned by the API but not rendered.
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

These criteria are acceptance for a local learning project only. Public and clinical use remain outside scope; conditional governance requirements are retained in [Safety and governance](safety-and-governance.md).
