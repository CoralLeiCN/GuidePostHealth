# NextStep NHS Guide RAG

NextStep is a local research prototype that retrieves reviewed NHS symptom guidance and uses a constrained Codex agent to explain sensible next steps. It is an information navigator for England, **not** a diagnostic or clinical triage product.

The repository contains:

- a curated, versioned manifest of 25 common NHS symptom guides;
- a polite text-only NHS ingestion pipeline;
- local embeddings from `sentence-transformers/all-MiniLM-L6-v2`;
- an in-memory Qdrant collection rebuilt at API startup;
- a modern FastAPI backend with a read-only Codex SDK answer harness;
- an extractive retrieval fallback when Codex is unavailable;
- a responsive React/Vinext chat interface with server-owned NHS citations.

Detailed as-built behaviour, requirements, safety gaps, and production gates are maintained in the [specification set](docs/README.md).

## Architecture

```text
browser chat
    │
    ▼
FastAPI validation + index readiness ──► deterministic emergency floor
    │
    ▼
sentence-transformers query embedding
    │
    ▼
in-memory Qdrant retrieval
    │  + urgent sections from matched guides
    ▼
read-only Codex synthesis ──► evidence-ID validation
    │                                │
    └── failure ─► source extracts ◄─┘
                     │
                     ▼
         structured response + NHS links
```

The [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) is primarily designed for coding-focused threads. It is kept behind a small `AnswerAgent` interface here, runs with the read-only sandbox, receives only the retrieved evidence, and has no application tools. This satisfies the requested Codex harness while making it straightforward to replace with a clinically governed model workflow later.

## Local setup

Requirements: Node.js 22+, [`uv`](https://docs.astral.sh/uv/), and a Codex login usable by the local Codex SDK.

```bash
# Install both runtimes
npm install
uv sync --dev

# Download the reviewed NHS pages into data/nhs/ (gitignored)
uv run python -m nhs_rag.ingestion.cli --contact "mailto:you@example.com"

# Terminal 1: API (one worker is required for in-memory Qdrant)
npm run dev:api

# Terminal 2: frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

Copy `.env.example` to `.env` to change models or endpoints. Set `NEXTSTEP_CODEX_ENABLED=false` to test retrieval-only mode. The first API start downloads the compact sentence-transformer model, then indexes the ignored local corpus.

## Commands

```bash
uv run pytest                         # backend tests
uv run ruff check backend tests       # Python lint
uv run mypy                           # Python types
npm run build                         # production frontend build
npm run lint                          # frontend lint
```

Refresh the corpus regularly:

```bash
uv run python -m nhs_rag.ingestion.cli --contact "mailto:you@example.com"
```

The fetcher uses an explicit allowlist, checks `robots.txt`, sends conditional requests, validates redirects, waits between pages, strips media and navigation, and keeps the previous file if a refresh fails. It does not recursively crawl links.

## API

- `POST /api/v1/chat` — retrieve evidence and return structured guidance.
- `GET /api/v1/sources` — list locally indexed guides and freshness metadata.
- `GET /api/v1/health/live` — process liveness.
- `GET /api/v1/health/ready` — corpus/index readiness.

Example request:

```json
{
  "message": "I have had a cough for five days",
  "history": []
}
```

Responses distinguish `codex`, `retrieval_only`, and `emergency` modes. Source titles and URLs come from the server-owned corpus; generated links are never trusted.

## Safety boundaries

This is deliberately a narrow engineering starter, not a deployable medical service.

- It does not diagnose, rule out conditions, or claim symptoms are harmless.
- Obvious danger wording is escalated before model generation; the rule never downgrades NHS urgency.
- Emergency and urgent chunks from matched pages are forced into the evidence bundle.
- Every generated next step or warning sign must reference a retrieved evidence ID.
- Invalid agent output, timeouts, missing citations, or unavailable authentication fall back to labelled source extracts.
- Symptom text is not intentionally logged or persisted; chat state stays in browser memory. Codex remains an external processing boundary that must be assessed for the intended deployment.
- The UI always exposes 999/111 guidance and the original NHS pages.

Before any public pilot, obtain clinical safety review, privacy/DPIA review, legal review, security testing, retrieval evaluation, and advice on UK medical-device regulation. A disclaimer is not a substitute for clinical governance.

## NHS content and attribution

The tracked manifest was selected from the [NHS Symptoms A–Z](https://www.nhs.uk/symptoms/). Downloaded, parsed pages live under `data/nhs/` and are excluded from Git. Gitignoring content does not itself resolve licensing obligations.

NHS website text is generally reusable under the Open Government Licence, subject to exclusions. This project ingests text only and intentionally strips NHS logos, images, video, third-party material, and interactive medical-device content. See the [NHS terms and conditions](https://www.nhs.uk/our-policies/terms-and-conditions/) and [content not licensed for reuse](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/).

> Contains public sector information licensed under the Open Government Licence v3.0.

AI-generated/adapted wording must never be presented as NHS-authored, clinically approved, or endorsed. Keep source links and copied-as-at dates visible, and refresh the local corpus frequently.

## Repository map

```text
app/                         React chat interface
backend/nhs_rag/
  agent/                     Codex prompt and harness
  ingestion/                 reviewed NHS fetch + parse pipeline
  retrieval/                 chunking, embeddings, Qdrant
  safety/                    deterministic escalation floor
config/nhs_sources.json      tracked source allowlist
data/nhs/                    downloaded corpus (ignored)
tests/                       parser, retrieval, safety, API tests
docs/                        product, architecture, safety, and operations specifications
```
