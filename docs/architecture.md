# System architecture

## 1. As-built overview

```text
NHS source manifest ──► polite fetch + text parser ──► ignored guide JSON files
                                                            │
                                                            ▼
Browser chat ──► FastAPI ──► readiness ──► emergency floor ──► query embedding
                                                                │
                                                                ▼
                                          standalone Qdrant cosine retrieval
                                                                │
                                             + urgent/emergency guide sections
                                                                ▼
                                          read-only ephemeral Codex synthesis
                                               │                 │
                                               │ failure         ▼
                                               └──────► extractive fallback
                                                                 │
                                                                 ▼
                                          evidence validation + NHS citations
```

The ingestion and indexing paths are run explicitly. API startup loads the local corpus and validates the existing standalone Qdrant collection.

## 2. Component responsibilities

| Component | Responsibility |
| --- | --- |
| `config/nhs_sources.json` | Versioned source allowlist and corpus scope. |
| `backend/nhs_rag/ingestion/` | Fetch NHS pages, validate network destinations, parse text and metadata, and write local guide JSON. |
| `backend/nhs_rag/retrieval/` | Chunk documents, create embeddings, build the Qdrant collection, and retrieve evidence. |
| `backend/nhs_rag/safety/` | Apply the narrow deterministic emergency phrase floor. |
| `backend/nhs_rag/agent/` | Build the constrained evidence prompt and adapt the Codex SDK to the `AnswerAgent` interface. |
| `backend/nhs_rag/service.py` | Orchestrate emergency handling, retrieval, synthesis/fallback, and citations. |
| `backend/nhs_rag/main.py` | Own FastAPI lifecycle, CORS, readiness, and HTTP routes. |
| `backend/nhs_rag/models.py` | Define corpus, evidence, agent, request, and response schemas. |
| `app/page.tsx` | Hold browser-session chat state and render the user experience. |

## 3. Serving sequence

1. FastAPI creates one `RagService`, one lazy sentence-transformer encoder, and one `CodexAnswerAgent`.
2. During application startup, `RagService.load_existing_index()` validates the collection metadata, corpus hash, embedding model, vector size, and point count.
3. Invalid guide JSON files are skipped. With no valid guides, readiness remains false.
4. A chat request is validated by Pydantic and rejected with `503` if the index is not ready.
5. `ChatService` checks the latest message against the emergency phrase floor.
6. Non-emergency messages are embedded and queried against Qdrant.
7. Codex receives recent history plus the selected evidence but no source URLs.
8. The server validates the structured draft and evidence IDs. Any agent exception selects the extractive fallback.
9. The server creates citations from corpus records and returns the typed response.

## 4. Runtime state

| State | Location | Lifetime |
| --- | --- | --- |
| Chat messages | Browser React memory | Current page session; cleared by reload or “New chat”. |
| Parsed NHS corpus | `data/nhs/*.json` | Local files; ignored by Git. |
| Embedding model | API process memory and library cache | Loaded lazily; process lifetime. |
| Qdrant collection | Standalone Docker service and named volume | Persists across API restarts; rebuilt only by the explicit index command. |
| Codex threads | Codex SDK | One ephemeral thread per attempted generated answer. |
| Codex runtime directory | `.codex-runtime/` | Local ignored directory. |

API processes can query the same standalone collection. The local Docker limits and lack of Qdrant authentication still make this a development topology, not a production deployment.

## 5. Trust boundaries

### Browser to API

Symptom text and recent history cross from the browser to FastAPI over HTTP. React does not persist the conversation, but this is not the same as local-only processing. A production deployment requires TLS, a correct privacy notice, request-size controls, abuse protection, and verified body redaction in infrastructure logs.

### API to Codex

When enabled, the latest question, up to 6 history items, and retrieved evidence cross an external model-processing boundary. The SDK thread is ephemeral, read-only, and deny-all, but provider terms, location, retention, training controls, and processor obligations still require formal review.

### Ingestion to NHS

The fetcher contacts only exact allowed NHS hosts and paths, validates redirects, checks `robots.txt`, and identifies itself. Parsed canonical URLs are not currently revalidated after HTML parsing, which is a trust-boundary gap to close.

### Local corpus to response

The indexer trusts locally stored, ignored guide JSON. Production ingestion requires integrity protection, versioning, provenance, validation of canonical/citation URLs, and a promotion process.

## 6. Configuration

Backend settings use the `GUIDEPOST_` prefix and load from the repository `.env` file. Browser-visible settings use `NEXT_PUBLIC_` because the frontend uses Next.js-compatible environment variables.

| Setting | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser API origin. |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | Metadata base URL. |
| `GUIDEPOST_CORPUS_DIR` | `data/nhs` | Parsed local corpus. |
| `GUIDEPOST_SOURCE_MANIFEST` | `config/nhs_sources.json` | Tracked source list. |
| `GUIDEPOST_COLLECTION_NAME` | `health_guidance` | Standalone Qdrant collection. |
| `GUIDEPOST_QDRANT_URL` | `http://127.0.0.1:6333` | Loopback-only local Qdrant endpoint. |
| `GUIDEPOST_QDRANT_TIMEOUT_SECONDS` | `5` | Request timeout. Range 1–60 seconds. |
| `GUIDEPOST_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Model name; revision is not pinned yet. |
| `GUIDEPOST_TOP_K` | `6` | Dense results requested. Range 1–20. |
| `GUIDEPOST_MAXIMUM_EVIDENCE_CHUNKS` | `9` | Final evidence cap. Range 1–20. |
| `GUIDEPOST_CODEX_ENABLED` | `true` | Disable for retrieval-only mode. |
| `GUIDEPOST_CODEX_MODEL` | `gpt-5.6-terra` | Current answer model default. |
| `GUIDEPOST_CODEX_RUNTIME_DIR` | `.codex-runtime` | Ignored working directory. |
| `GUIDEPOST_CODEX_TIMEOUT_SECONDS` | `75` | Allowed range 5–300 seconds. |
| `GUIDEPOST_CODEX_MAX_CONCURRENCY` | `2` | Process-local semaphore, allowed range 1–8. |
| `GUIDEPOST_CORS_ORIGINS` | localhost port 3000 | Development origins only. |

## 7. Design decisions

### Resource-limited standalone Qdrant for local development

Docker Compose runs Qdrant with 0.5 CPU, 256 MiB RAM, loopback-only port exposure, and persistent storage and snapshot volumes. This supports the small corpus without embedding vector state in the API process. Authentication, encryption, backup/restore, and controlled index promotion are still required for production.

### Local sentence-transformer embeddings

The compact model avoids a separate embedding API and keeps corpus embedding local. Production evaluation must determine whether its retrieval quality is adequate, and the exact model revision must be pinned.

### Replaceable answer agent

`AnswerAgent` separates retrieval and API behaviour from Codex. The current Codex harness meets the agentic requirement while allowing a clinically governed model workflow to replace it without redesigning ingestion or retrieval.

### Ignored downloaded corpus

Git tracks source selection and reproducible ingestion logic, not copied NHS text. This reduces repository churn and redistribution risk, but it does not by itself satisfy licensing, freshness, provenance, or deployment requirements.

## 8. Deployment status

The application is currently intended for local development. `.openai/hosting.json` contains hosting project metadata, but the frontend/backend and corpus have not been published as a public service. No production topology, environment, data region, secret store, domain, TLS policy, or operational owner has been approved.
