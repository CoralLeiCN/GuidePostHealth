# Operations and roadmap

## 1. Local development runbook

### Prerequisites

- Node.js 22.13 or newer.
- Python 3.11 or newer.
- `uv`.
- Network access for dependency/model download and NHS corpus refresh.
- A Codex login usable by the local Python SDK when generated mode is enabled.

### Install

```bash
npm install
uv sync --dev
```

### Build the ignored corpus

```bash
uv run python -m nhs_rag.ingestion.cli --contact "mailto:you@example.com"
```

Use a real monitored contact address or project URL for anything beyond individual development.

### Start the services

```bash
# Terminal 1
npm run dev:api

# Terminal 2
npm run dev
```

Open `http://localhost:3000`. OpenAPI documentation is at `http://localhost:8000/docs`.

The API must run with one worker while Qdrant remains in memory.

### Retrieval-only mode

Set this in `.env`:

```dotenv
NEXTSTEP_CODEX_ENABLED=false
```

Restart the API. Successful chats will report `retrieval_only` and return source extracts.

## 2. Refresh behaviour

Run ingestion again to refresh the local files, then restart the API so it rebuilds the in-memory index.

```bash
uv run python -m nhs_rag.ingestion.cli --contact "mailto:you@example.com"
```

The current process has no scheduler, live re-index endpoint, corpus promotion environment, or automatic stale-content alarm.

## 3. Verification commands

```bash
uv run pytest
uv run ruff check backend tests
uv run mypy
npm run lint
npm run build
```

The initial implementation baseline passed all commands. The Python suite currently expands to 13 passing test cases and covers:

- parser section extraction, media removal, and urgency labels;
- URL allowlist validation;
- Qdrant retrieval plus urgent-section augmentation;
- emergency bypass and one simple negation case;
- retrieval-only fallback;
- readiness/chat response shape; and
- too-short chat input rejection.

## 4. Missing verification

| Area | Missing evidence |
| --- | --- |
| Clinical safety | Clinically authored scenario set, hazard coverage, signed thresholds, subgroup performance, and false-reassurance analysis. |
| Retrieval | Real-query recall benchmark, hybrid/reranker comparison, stale/removed-source tests, and embedding-revision evaluation. |
| Agent | Direct contract tests for every malformed/unsupported output, semantic entailment evaluation, urgency non-downgrade, and prompt-injection suite. |
| Ingestion | Live integration test, canonical URL validation, structural-change alerts, licence exclusions, orphan removal, and reproducibility test. |
| Frontend | Component, integration, end-to-end, accessibility, cross-browser, mobile, timeout, cancellation, and offline recovery tests. |
| API/operations | Load, concurrency, rate limit, security, privacy/log-redaction, dependency, failure-recovery, and disaster-recovery tests. |

## 5. Current operational limits

- No public deployment or approved production environment.
- No persistent/shared vector index; every API process builds its own copy.
- Startup downloads/loads the embedding model and indexes the entire corpus.
- No zero-downtime index swap, backup, restore, or rollback.
- No authentication, rate limiting, queue, user quota, or distributed concurrency control.
- Only the Codex call has an explicit timeout; there is no full-request deadline or browser cancellation.
- No structured privacy-safe telemetry, alerting, dashboards, service objectives, or on-call runbook.
- No durable conversation, and `conversation_id` is not used.
- No automated corpus refresh, diff review, or freshness enforcement.
- CORS defaults and development servers are not a production security configuration.

## 6. Roadmap

### Milestone 0 — local engineering MVP

Status: **Implemented**.

- Git repository and dependency locks.
- Curated manifest and ignored local corpus.
- Safe-network ingestion and text parser.
- Section-aware embeddings and in-memory Qdrant retrieval.
- Constrained Codex adapter and extractive fallback.
- FastAPI endpoints and responsive browser chat.
- Initial engineering tests, lint, type checks, and builds.
- As-built specification set.

### Milestone 1 — safety and product definition

Status: **Required before public pilot**.

1. Approve intended purpose, users, exclusions, content scope, and claims.
2. Appoint clinical safety, privacy, regulatory, legal, security, accessibility, and operational owners.
3. Create the hazard log, safety case/plan, DPIA, regulatory assessment, threat model, and content-use assessment.
4. Fix the readiness-before-emergency path and strengthen response-level grounding/urgency rules.
5. Build the clinically authored evaluation and release thresholds.

### Milestone 2 — reproducible content and retrieval

Status: **Required before public pilot**.

1. Version, sign, and promote corpus/index artifacts.
2. Automate refresh, diff review, orphan deletion, freshness alerts, rollback, and takedown.
3. Pin the embedding revision and evaluate dense, hybrid, and reranked retrieval options.
4. Migrate to persistent Qdrant with authentication, encryption, backup/restore, and blue/green index promotion.

### Milestone 3 — production service controls

Status: **Required before public pilot**.

1. Select an approved hosting/data region and deploy TLS, secrets, least privilege, network controls, and hardened images.
2. Add appropriate authentication/abuse controls, full-request timeouts, cancellation, backpressure, and provider circuit breaking.
3. Add privacy-safe observability, service objectives, alerts, runbooks, incident response, rollback, and disaster recovery.
4. Correct privacy/source-freshness UI copy and add dynamic readiness/source state.
5. Complete frontend/E2E/accessibility/security/load testing.

### Milestone 4 — controlled pilot decision

Status: **Blocked**.

1. Run the versioned release candidate through all safety and quality gates.
2. Resolve every unacceptable hazard and regression.
3. Exercise incident, rollback, source-takedown, and model/provider-outage procedures.
4. Obtain written approval from every required governance owner.
5. Pilot only within the approved users, claims, geography, monitoring, and support model.

## 7. Open decisions

| Decision | Why it matters |
| --- | --- |
| Exact intended purpose and population | Drives evidence, claims, safety controls, and regulatory assessment. |
| Whether Codex is acceptable for production health-text processing | Drives privacy, provider, retention, region, and model-governance controls. |
| Persistent Qdrant hosting model | Drives availability, data location, access control, cost, backup, and ownership. |
| Corpus refresh and clinical diff-approval service level | Drives freshness, staffing, takedown, and availability behaviour. |
| Conversation retention | The safest default is none; any persistence needs a specific purpose and user controls. |
| Authentication and audience | A private research cohort and an anonymous public service have different abuse, privacy, and support needs. |
| Supported children/pregnancy pathways | Current source presence does not establish complete or safe population coverage. |
| Success and safety thresholds | They must be agreed before evaluation, not selected after results are seen. |

## 8. Definition of done

### Local MVP

Done when setup is reproducible, the corpus can be ingested, the services run, responses are cited or explicitly fallback, and all engineering checks pass.

### Public pilot

Done only when the release gate in [Safety and governance](safety-and-governance.md) is satisfied and the approved release can be operated, monitored, stopped, rolled back, and audited without exposing symptom content.

### Clinical use

Not defined for this repository. It requires a separate scope, evidence plan, regulatory/governance decision, and deployment agreement.
