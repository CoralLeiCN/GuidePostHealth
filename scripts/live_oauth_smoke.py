"""Opt-in smoke test using ChatGPT OAuth, live NHS pages, embeddings, and Qdrant."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from uuid import uuid4

from fastapi.testclient import TestClient
from nhs_rag.agent.codex import CodexAnswerAgent
from nhs_rag.main import create_app
from nhs_rag.retrieval.embedder import SentenceTransformerEncoder
from nhs_rag.retrieval.service import RagService
from nhs_rag.settings import Settings
from openai_codex import AsyncCodex, CodexConfig
from qdrant_client import QdrantClient

from cronjobs.nhs_dataset.downloader import ingest_sources, load_sources


async def verify_oauth(model: str) -> None:
    async with AsyncCodex(
        config=CodexConfig(
            client_name="guidepost_health",
            client_title="GuidePost Health",
        )
    ) as codex:
        account = await codex.account()
        if account.account is None or account.account.root.type != "chatgpt":
            raise RuntimeError("This test requires an existing ChatGPT OAuth login")
        if model not in {item.model for item in (await codex.models()).data}:
            raise RuntimeError(f"Requested model is unavailable: {model}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--report", type=Path, default=Path("outputs/live-oauth-smoke.json"))
    args = parser.parse_args()
    asyncio.run(verify_oauth(args.model))
    print(f"Verified ChatGPT OAuth and model availability: {args.model}", flush=True)

    settings = Settings(
        _env_file=None, codex_model=args.model, codex_base_url=None, codex_api_key=None
    )
    sources = [
        source
        for source in load_sources(Path("config/nhs_sources.json"))
        if urlparse(source.url).path.rstrip("/").split("/")[-1]
        in {"cough", "headaches", "sore-throat"}
    ]
    if len(sources) != 3:
        raise RuntimeError("The three smoke-test sources must be present in the reviewed manifest")
    collection = f"guidepost_live_test_{uuid4().hex}"
    results: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="guidepost-live-") as directory:
        root = Path(directory)
        ingestion = asyncio.run(
            ingest_sources(
                sources,
                output_dir=root / "corpus",
                raw_dir=root / "raw",
                contact="http://localhost/guidepost-health-research-prototype",
            )
        )
        if ingestion.failed or ingestion.fetched != len(sources):
            raise RuntimeError(f"Live NHS ingestion failed: {ingestion.errors}")
        print(f"Fetched and parsed {ingestion.fetched} live NHS pages", flush=True)
        rag = RagService(
            corpus_dir=root / "corpus",
            collection_name=collection,
            encoder=SentenceTransformerEncoder(settings.embedding_model),
            embedding_model=settings.embedding_model,
            client=QdrantClient(url=args.qdrant_url, check_compatibility=False),
        )
        try:
            rag.index_corpus()
            print(f"Indexed {rag.chunk_count} chunks with real embeddings in Qdrant", flush=True)
            agent = CodexAnswerAgent(
                model=args.model,
                timeout_seconds=settings.codex_timeout_seconds,
                max_concurrency=1,
                runtime_dir=root / "codex-runtime",
            )
            app = create_app(settings=settings, rag=rag, agent=agent)
            question = (
                "Fictional test example: an otherwise healthy adult has a mild dry cough. "
                "They can breathe normally and have no chest pain or fever. "
                "What next steps does the supplied NHS guidance suggest?"
            )
            with TestClient(app) as client:
                assert client.get("/api/v1/health/ready").status_code == 200
                history: list[dict[str, str]] = []
                for name, message in [("initial", question), ("follow_up", "Five days.")]:
                    started = time.monotonic()
                    response = client.post(
                        "/api/v1/chat", json={"message": message, "history": history}
                    )
                    assert response.status_code == 200, response.status_code
                    body = response.json()
                    assert body["mode"] == "codex", f"{name}: fallback does not count as a pass"
                    assert body["evidence_status"] == "references_checked"
                    assert body["sources"] and body["summary"]
                    assert all(
                        urlparse(source["url"]).hostname == "www.nhs.uk"
                        for source in body["sources"]
                    )
                    assert any("cough" in source["url"] for source in body["sources"])
                    results.append(
                        {
                            "case": name,
                            "seconds": round(time.monotonic() - started, 2),
                            "response": body,
                        }
                    )
                    history.extend(
                        [
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": body["summary"]},
                        ]
                    )
                    print(f"PASS {name}: live {args.model}, validated NHS references", flush=True)
                rag.ready = False
                response = client.post(
                    "/api/v1/chat", json={"message": "No cough but I cannot breathe"}
                )
                assert response.status_code == 200
                assert response.json()["mode"] == "emergency"
                assert response.json()["evidence_status"] == "fixed_guidance"
                results.append({"case": "emergency_without_index", "response": response.json()})
                print("PASS emergency bypass with unavailable index", flush=True)
        finally:
            rag.close()
            cleanup = QdrantClient(url=args.qdrant_url, check_compatibility=False)
            try:
                if cleanup.collection_exists(collection):
                    cleanup.delete_collection(collection)
            finally:
                cleanup.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {"auth_type": "chatgpt", "model": args.model, "passed": True, "results": results},
            indent=2,
        )
        + "\n"
    )
    print(f"PASS live OAuth smoke test; report: {args.report}", flush=True)


if __name__ == "__main__":
    main()
