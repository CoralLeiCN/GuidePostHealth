# Offline jobs

This package contains scheduled ETL and one-off data-build workflows. It is deliberately
separate from the FastAPI service in `backend/nhs_rag/`.

## Shared guide workflow

See the separate [NHS](../docs/guide-data-workflow.md#nhs-processing-graph) and
[Mayo](../docs/guide-data-workflow.md#mayo-processing-graph) processing graphs for acquisition,
raw archives, guide processing, exports and retrieval. `raw_archive.py` owns
the HTML-plus-metadata format used by both NHS and Mayo download jobs.

Mayo acquisition only (implementation reference): read the
[Mayo compliance review](../docs/mayo-dataset-compliance.md) first. Further acquisition,
imports or processing require recorded clearance; the current commands do not enforce it.
Browser capture is not a permission or access-restriction workaround.

```bash
uv run python -m cronjobs.mayo_dataset --contact "mailto:you@example.com"
uv run python -m cronjobs.mayo_dataset --from-browser data/raw/mayo/browser-captures
```

This writes `data/raw/mayo/` and exits without parsing guides, exporting datasets or indexing.
The existing experimental Mayo parser remains separate; its integration with the new raw
archive is future work. Neither job is automatically scheduled by being in this directory.

## NHS symptom dataset

For the full technical contract and human review procedure, see the
[dataset creation workflow and extraction specification](../docs/nhs-dataset-workflow.md).
Both guide parsing and index discovery require exactly one `main#maincontent` and reject
missing or ambiguous regions with a schema error; there is no generic-main fallback.
The full job exits nonzero and skips export on a page failure. Review the error and archived
source before changing the parser. Deferred improvements are tracked in [backlog.md](../backlog.md).

This project uses the corpus for local LLM testing and learning RAG. It is not designed
or intended for any public or clinical use. Use fictional test questions, not real patient
information. The intended-use statement does not change the underlying content licence.

The generated data is an **adapted reference corpus**, not an unchanged or clinically approved
NHS publication. Preserve `NOTICE.md` with the dataset. Read the
[compliance review](../docs/nhs-dataset-compliance.md) before redistribution; page-level
rights clearance remains pending. Existing local exports must be regenerated to acquire the
corrected disclosures. Hub transfers require the notice file and exclude raw HTML.

Configure the future Hugging Face destination in the Git-ignored local file:

```bash
cp config/huggingface.example.json config/huggingface.local.json
```

```json
{
  "namespace": "your-username-or-organisation",
  "dataset_name": "nhs-symptom-guides",
  "private": true
}
```

This configuration changes the repository ID written into the generated dataset card. It does
not authenticate or upload the dataset. Hugging Face credentials must never be stored in this
file.

Authenticate using Hugging Face's credential store or the `HF_TOKEN` environment variable:

```bash
hf auth login
```

Upload the completed local dataset:

```bash
uv run python -m cronjobs.nhs_dataset.hub upload
```

Download the configured dataset into the local Git-ignored dataset directory:

```bash
uv run python -m cronjobs.nhs_dataset.hub download
```

These transfer commands communicate only with Hugging Face. They do not import or invoke NHS
discovery, downloading, or parsing code. Upload is restricted to the dataset card, content
notice, build metadata, and the two JSONL data files; raw HTML and the parsed application corpus are never
uploaded.

Refresh the already-discovered NHS corpus:

```bash
uv run python -m cronjobs.nhs_dataset.refresh --contact "mailto:you@example.com"
```

Rediscover the live NHS Symptoms A-to-Z index, download each unique guide once, and build the
local Hugging Face dataset repository. Each successful response is also retained as compressed
raw HTML with response metadata:

```bash
uv run python -m cronjobs.nhs_dataset --contact "mailto:you@example.com"
```

Rebuild the parsed corpus and Hugging Face dataset entirely from the raw archive, without
accessing NHS.uk:

```bash
uv run python -m cronjobs.nhs_dataset --from-raw
```

The job owns its manifest, Hub configuration, raw archive, parsed corpus, and export paths. Use
`--manifest-path`, `--hub-config`, `--raw-dir`, `--corpus-dir`, and `--output-dir` to override
their repository defaults. Use a monitored email address or project URL in `--contact` for a
scheduled run.

Raw HTML is stored under `data/raw/nhs/` as `.html.gz` files. A matching `.metadata.json`
stores the requested and final URLs, redirect chain, fetch time, response headers, encoding,
byte length, and SHA-256 checksum. Both the raw and derived data directories are Git-ignored.

The backend shares only the validated guide schema and reads completed corpus artifacts; it
does not discover, fetch, parse, or export NHS pages.
