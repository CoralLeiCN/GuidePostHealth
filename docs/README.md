# GuidePost Health specification set

These documents describe the system that exists in this repository and the work still required before it can be considered for public or clinical use.

The baseline is version `0.1.0`, reviewed against the code and local corpus on 31 August 2026. If a document and executable code disagree, the code is the as-built truth and the document must be corrected in the same change.

## Status language

| Status | Meaning |
| --- | --- |
| **Implemented** | Present in the repository and exercised by the current test or build workflow. It does not imply clinical approval. |
| **Required** | A release condition that is not complete. Public use remains blocked while any required item is open. |
| **Proposed** | A design direction that still needs an owner or decision. |
| **Out of scope** | Deliberately excluded from the current research prototype. |

## Current implementation snapshot

| Area | As built |
| --- | --- |
| Product | Local, England-focused NHS information navigator; not a diagnostic or clinical triage service. |
| Corpus | A tracked manifest of 25 NHS symptom/condition URLs and an ignored local snapshot of 25 parsed documents, 205 sections, and 207 chunks. |
| Retrieval | Normalised Sentence Transformer embeddings and persistent standalone Qdrant cosine search. |
| Answering | A constrained, read-only Codex synthesis step with evidence-ID checks and an extractive fallback. |
| Safety | A narrow deterministic emergency phrase rule, forced urgent evidence from matched guides, fixed 999/111 UI copy, and server-owned citations. |
| Backend | FastAPI with chat, source inventory, liveness, and readiness endpoints. |
| Frontend | Responsive React/Vinext chat with loading, error, emergency, citation, and retrieval-only states. |
| Verification | 13 Python tests plus Python lint/type checks and frontend lint/build checks passed for the initial implementation. |
| Deployment | Local development only. Hosting project metadata exists, but no public application has been published. |

“Reviewed guide” in the interface refers to the source page metadata and curated source list. It does **not** mean that this project, its retrieval behaviour, or its generated answers have received clinical review.

## Requested scope coverage

| Requested capability | Status | Current result |
| --- | --- | --- |
| Start a Git repository | Implemented | Repository is initialised on `main` with locked Python and Node dependencies. |
| Find common NHS symptom guides | Implemented | `config/nhs_sources.json` contains 25 curated NHS symptom/condition pages. |
| Store downloaded guides locally but ignore them in Git | Implemented | Parsed JSON is under ignored `data/nhs/`; selection and ingestion code remain tracked. |
| Build RAG over the guides | Implemented | Section-aware chunking, local embeddings, dense retrieval, urgent-section augmentation, and citations. |
| Run standalone Qdrant locally | Implemented | A resource-limited Docker service persists the explicitly indexed collection in a named volume. |
| Harden Qdrant for production | Required for production | Authentication, encryption, index promotion, backup, and restore remain open. |
| Use a simple Transformer embedding model | Implemented | `sentence-transformers/all-MiniLM-L6-v2`, loaded locally and configured by environment. |
| Use Codex as the agent harness | Implemented | Read-only ephemeral Codex threads behind a replaceable `AnswerAgent` protocol. |
| Build a modern Python backend | Implemented | Typed FastAPI service with readiness, source inventory, and structured chat endpoints. |
| Build a chat frontend | Implemented | Responsive React/Vinext interface with citations and safety/fallback states. |
| Make it suitable for public health use | Not yet authorised | The safety, clinical, privacy, regulatory, legal, security, accessibility, and operations gates remain required. |

## Documents

1. [Product specification](product-spec.md) — intended use, users, scope, journeys, requirements, and current UX.
2. [System architecture](architecture.md) — components, runtime flow, trust boundaries, configuration, and design decisions.
3. [Corpus and RAG specification](corpus-and-rag.md) — source policy, ingestion, parsing, chunking, indexing, and retrieval.
4. [API and agent contract](api-and-agent.md) — HTTP schemas, modes, Codex constraints, citation handling, and failure semantics.
5. [Safety and governance](safety-and-governance.md) — implemented safeguards, known hazards, and release-blocking governance work.
6. [Operations and roadmap](operations-and-roadmap.md) — setup, verification, operational limits, milestones, and definitions of done.

## Decision summary

- The current milestone is an engineering MVP that can be run and evaluated locally.
- Downloaded NHS text remains outside Git; the reviewed URL manifest and the ingestion code are versioned.
- Qdrant runs as a resource-limited persistent local service. Authentication, encryption, and operational controls are required for production.
- Codex is an interchangeable answer harness, not the source of health facts. It receives retrieved evidence and must not supply URLs.
- Public pilot is blocked by clinical governance, safety evaluation, regulatory assessment, privacy/DPIA, licensing, security, accessibility, and production operations work.
- Clinical use remains out of scope unless the product is deliberately re-scoped and the applicable evidence and governance obligations are met.
