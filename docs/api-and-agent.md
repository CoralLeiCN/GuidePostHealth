# API and agent contract

## 1. Base service

The development API listens at `http://localhost:8000`. Interactive OpenAPI documentation is available at `/docs` while the service is running.

Default CORS policy permits `http://localhost:3000` and `http://127.0.0.1:3000`, disables credentials, permits only `GET` and `POST`, and permits only the `Content-Type` request header.

## 2. Endpoints

| Method and path | Success | Failure |
| --- | --- | --- |
| `GET /api/v1/health/live` | `200` health body; `status` may be `not_ready`. | No explicit application failure mode. |
| `GET /api/v1/health/ready` | `200` when the index is ready. | `503` when no ready index exists. |
| `GET /api/v1/sources` | `200` source inventory. | `503` until the index is ready. |
| `POST /api/v1/chat` | `200` structured answer. | `422` for schema validation; `503` until the index is ready. |

### Health response

```json
{
  "status": "ok",
  "documents": 25,
  "chunks": 207,
  "agent": "codex",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

`status` is `ok` or `not_ready`. `agent` reports configured availability (`codex` or `retrieval_only`), not the mode of an individual request.

### Source summary

Each source inventory item contains `title`, canonical `url`, `fetched_at`, optional `last_reviewed`, and the number of parsed `sections`.

## 3. Chat request

```json
{
  "message": "I have had a cough for five days",
  "history": [
    {"role": "user", "content": "It started on Monday"},
    {"role": "assistant", "content": "How are you feeling otherwise?"}
  ],
  "conversation_id": null
}
```

| Field | Contract |
| --- | --- |
| `message` | Required string, 2–2,000 characters. Whitespace is collapsed before processing. |
| `history` | Optional list, at most 10 messages. |
| `history[].role` | `user` or `assistant`. |
| `history[].content` | 1–4,000 characters. |
| `conversation_id` | Optional string up to 100 characters; accepted but currently unused. |

The frontend sends at most 8 prior rendered messages. The prompt keeps at most the last 6.

## 4. Chat response

```json
{
  "request_id": "87faeb25-0de0-4c1f-a8ce-98ff16f9af70",
  "mode": "codex",
  "grounded": true,
  "urgency": "routine",
  "summary": "The retrieved NHS guidance suggests monitoring the cough and using the listed self-care steps.",
  "next_steps": ["Rest and drink plenty of fluids."],
  "warning_signs": ["Use the urgent route described by the NHS source if you feel very unwell."],
  "follow_up_question": "Are you short of breath?",
  "sources": [
    {
      "id": "retrieved-chunk-id",
      "title": "Cough",
      "section": "Things you can try",
      "url": "https://www.nhs.uk/symptoms/cough/",
      "fetched_at": "2026-08-30T23:40:31Z",
      "excerpt": "Source excerpt..."
    }
  ],
  "notice": "AI-generated guidance based on retrieved NHS information. It is not a diagnosis."
}
```

The example illustrates shape only; it is not a clinically approved answer.

| Field | Contract |
| --- | --- |
| `request_id` | Server-generated UUID string. |
| `mode` | `codex`, `retrieval_only`, or `emergency`. |
| `grounded` | `true` when the server emitted at least one citation. |
| `urgency` | `emergency`, `urgent`, `routine`, `self_care`, or `unknown`. |
| `summary` | Plain-language result. |
| `next_steps` | Zero or more action strings. |
| `warning_signs` | Zero or more escalation strings. |
| `follow_up_question` | One optional question. |
| `sources` | At most 6 server-created citations. |
| `notice` | Mode-specific safety/provenance copy. |

## 5. Response modes

### `emergency`

A recognised, non-negated emergency phrase returns before retrieval or model generation, provided the index has already passed the route readiness check. The body contains a fixed 999/A&E message and the server-owned NHS “When to call 999” link.

### `codex`

Retrieval succeeded and Codex returned a schema-valid draft whose next steps and warning signs use only known evidence IDs. This mode does not mean clinically validated or fully entailed.

### `retrieval_only`

Retrieval succeeded but generation was disabled or raised any exception. The server returns labelled excerpts, reports urgency as `unknown`, and does not claim personalised synthesis.

## 6. Codex answer harness

`CodexAnswerAgent` implements the replaceable `AnswerAgent` protocol.

For each attempted answer it:

- starts one ephemeral Codex thread;
- uses `gpt-5.6-terra` by default;
- sets approval mode to deny all;
- uses a read-only sandbox rooted at the ignored `.codex-runtime` directory;
- supplies no application tools;
- limits process-local concurrent calls to 2 by default;
- applies a 75-second timeout by default; and
- extracts and validates one JSON object from the final response.

The prompt supplies:

- rules that prohibit diagnosis, certainty, unsupported claims, medicine doses, tools, shell, filesystem, and network use;
- the last 6 chat-history entries as untrusted JSON;
- the latest user question;
- retrieved evidence IDs, titles, sections, urgency labels, and text; and
- the required JSON shape.

It deliberately omits source URLs. The API reconstructs citations from trusted corpus objects.

## 7. Agent draft schema

The model draft contains:

- `summary`: 1–1,500 characters;
- `help_level`: one supported urgency value;
- at most 6 `next_steps`;
- at most 6 `warning_signs`;
- up to 4 evidence IDs per step or warning; and
- one optional follow-up question up to 400 characters.

The server rejects a step or warning when it has no evidence ID or contains an ID outside the retrieved bundle. It does not currently verify semantic entailment, require a citation for the summary/follow-up, or prove that `help_level` matches source urgency.

## 8. Fallback and error semantics

The chat orchestrator catches all exceptions from the answer agent, including disabled mode, timeout, authentication/SDK failure, missing final output, malformed JSON, schema failure, and invalid evidence references. It then selects retrieval-only output.

The current broad catch protects the user experience but does not log a privacy-safe operational event or distinguish capacity, authentication, validation, and provider failures. Production must add typed errors, safe metrics, alerting, and end-to-end request timeouts without logging symptom content.

The route does not catch retrieval or embedding errors. Those currently become server errors. Full production failure behaviour, retry rules, and circuit breaking are still required.

