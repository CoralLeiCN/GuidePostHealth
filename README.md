# GuidePost Health

GuidePost Health is a **local project for LLM testing and learning retrieval-augmented generation (RAG)**. NHS website text is the example corpus for experimenting with extraction, chunking, embeddings, retrieval, citations and model responses.

**It is not designed or intended for any public use, personal health guidance or clinical use.** Use fictional test questions, not real patient information. A public service or clinical application is outside this project's scope; pursuing one would require a separate scope decision and appropriate privacy, clinical and other reviews.

The repository contains:

- a reproducible manifest of every unique guide linked from the NHS Symptoms A-to-Z index;
- a polite text-only NHS ingestion pipeline;
- local embeddings from `sentence-transformers/all-MiniLM-L6-v2`;
- a persistent standalone Qdrant service with a resource-limited Docker setup;
- a modern FastAPI backend with a read-only Codex SDK answer harness;
- an extractive retrieval fallback when Codex is unavailable;
- a responsive React/Vinext chat interface with server-owned NHS citations.

Detailed as-built behaviour, requirements, safety gaps, and production gates are maintained in the [specification set](docs/README.md).
The [dataset creation workflow](docs/nhs-dataset-workflow.md) documents the full extraction
pipeline, technical contracts, known information loss and decisions for human review.
Open work and deferred decisions are tracked in [backlog.md](backlog.md).

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
standalone Qdrant retrieval
    │  + urgent sections from matched guides
    ▼
read-only Codex synthesis ──► evidence-ID validation
    │                                │
    └── failure ─► source extracts ◄─┘
                     │
                     ▼
         structured response + NHS links
```

The [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) is kept behind a small `AnswerAgent` interface here, runs with the read-only sandbox, receives retrieved evidence and has no application tools. The replaceable interface supports experiments with different answer models and RAG approaches.

## Local setup

Requirements: Node.js 22+, [`uv`](https://docs.astral.sh/uv/), Docker Compose, and either a
Codex login usable by the local Codex SDK or an OpenAI Responses-compatible model endpoint.

```bash
# Install both runtimes
npm install
uv sync --dev

# Download the reviewed NHS pages into data/nhs/ (gitignored)
uv run python -m cronjobs.nhs_dataset.refresh --contact "mailto:you@example.com"

# Start the resource-limited standalone Qdrant service
npm run qdrant:up

# Explicitly build the persistent Qdrant collection
npm run qdrant:index

# Terminal 1: API
npm run dev:api

# Terminal 2: frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

Copy `.env.example` to `.env` to change models or endpoints. Set `GUIDEPOST_CODEX_ENABLED=false` to test retrieval-only mode. The indexing command downloads the compact sentence-transformer model on first use and rebuilds the collection explicitly.

Qdrant listens only on `127.0.0.1:6333` and persists its collection in a Docker named volume. The container is capped at 0.5 CPU and 256 MiB RAM, which is ample for the small local corpus. API startup validates the existing collection against the local corpus and embedding model; it never silently creates, replaces, or accepts a stale collection. Run `npm run qdrant:index` after refreshing the corpus or changing the embedding model. Stop Qdrant without deleting its data with `npm run qdrant:down`; use `docker compose down --volumes` only when you intentionally want to remove the stored collection and snapshots. If the API later runs in the same Compose network, set `GUIDEPOST_QDRANT_URL=http://qdrant:6333`.

### OpenAI-compatible model endpoints

The answer harness can point its Codex runtime at a hosted or local custom endpoint without
changing your user-level Codex configuration:

```bash
GUIDEPOST_CODEX_MODEL=your-model-id
GUIDEPOST_CODEX_BASE_URL=https://your-provider.example/v1
GUIDEPOST_CODEX_API_KEY=replace-me
```

For a local server that does not require authentication, omit
`GUIDEPOST_CODEX_API_KEY`:

```bash
GUIDEPOST_CODEX_MODEL=your-local-model-id
GUIDEPOST_CODEX_BASE_URL=http://127.0.0.1:11434/v1
```

The Codex custom-provider transport uses `POST /responses` with streaming. An endpoint that
only implements `POST /chat/completions` is not sufficient even if it is otherwise described
as OpenAI-compatible. When the endpoint is unavailable or its output fails validation, the
application continues to return the labelled retrieval-only fallback.

## Commands

```bash
docker compose config                  # validate the Qdrant service definition
npm run qdrant:up                     # start Qdrant and wait until it is ready
npm run qdrant:index                  # explicitly rebuild the persistent collection
npm run qdrant:down                   # stop Qdrant and retain its named volumes
uv run pytest                         # Python tests
uv run ruff check backend cronjobs tests # Python lint
uv run mypy                           # Python types
npm run build                         # production frontend build
npm run lint                          # frontend lint
```

Refresh the corpus regularly:

```bash
uv run python -m cronjobs.nhs_dataset.refresh --contact "mailto:you@example.com"
```

Build a complete, deduplicated Hugging Face dataset repository (discovery, download, and
export) while retaining compressed raw HTML with fetch metadata:

```bash
uv run python -m cronjobs.nhs_dataset --contact "mailto:you@example.com"
```

Set the future Hugging Face username or organisation, repository name, and visibility in the
Git-ignored `config/huggingface.local.json`. Start from
`config/huggingface.example.json`; do not put an access token in this file. The build uses the
configured repository ID in the dataset card but does not upload anything.

Rebuild the parsed corpus and dataset later without accessing NHS.uk:

```bash
uv run python -m cronjobs.nhs_dataset --from-raw
```

After setting `namespace` in the Git-ignored `config/huggingface.local.json`, transfer the
generated dataset without accessing NHS.uk:

```bash
uv run python -m cronjobs.nhs_dataset.hub upload
uv run python -m cronjobs.nhs_dataset.hub download
```

Hugging Face authentication comes from `hf auth login` or `HF_TOKEN`; tokens are not stored in
the repository configuration.

The generated repository is written to `data/huggingface/nhs_symptom_guides/` and contains
`guides` (one record per unique destination page) and `sections` (one record per parsed
section) configurations. Exact A-to-Z index labels and medical/everyday aliases are retained
on the deduplicated guide record. The generated content is gitignored because its freshness
and reuse obligations differ from the application source code.

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

Public pilots and clinical deployment are out of scope, not planned release milestones. The privacy and clinical review requirements recorded in the governance documents apply to any separately proposed expansion into those uses. Local experimentation does not remove content-licence obligations or justify using real patient data.

## NHS content and attribution

The tracked manifest was selected from the [NHS Symptoms A–Z](https://www.nhs.uk/symptoms/). Downloaded, parsed pages live under `data/nhs/` and are excluded from Git. Gitignoring content does not itself resolve licensing obligations.

Eligible NHS website text is reusable under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), subject to the [NHS terms and conditions](https://www.nhs.uk/our-policies/terms-and-conditions/) and [exclusions](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/). The parser removes media and interactive elements, but this does not establish clearance for all third-party text. Raw HTML retains excluded markup and must not be redistributed as an OGL-only dataset.

> Contains public sector information licensed under the Open Government Licence v3.0.

Parsed records, isolated sections, shortened extracts and AI answers are treated as GuidePost Health adaptations. Original-page links identify provenance, not NHS authorship of the adaptation. Per-record attribution, licence links, fetch dates and adaptation notices travel with the export; its `NOTICE.md` must accompany Hub transfers. Apache-2.0 covers project software and does not relicense NHS content.

See the [NHS dataset compliance review](docs/nhs-dataset-compliance.md) for evidence, fixes and remaining release conditions. The local corpus has **not** received page-level rights clearance or clinical approval. No specific fee may be charged for access to NHS content; downstream health-data processing needs its own privacy compliance.

## Repository map

```text
app/                         React chat interface
backend/nhs_rag/
  agent/                     Codex prompt and harness
  retrieval/                 chunking, embeddings, Qdrant
  safety/                    deterministic escalation floor
cronjobs/nhs_dataset/        NHS discovery, download, parsing, and Hugging Face export
config/nhs_sources.json      tracked deduplicated A-to-Z source manifest and aliases
data/nhs/                    downloaded corpus (ignored)
data/raw/nhs/                compressed raw HTML and response metadata (ignored)
tests/                       parser, retrieval, safety, API tests
docs/                        product, architecture, safety, and operations specifications
```
