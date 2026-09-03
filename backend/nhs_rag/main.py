from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from nhs_rag.agent.codex import AnswerAgent, CodexAnswerAgent
from nhs_rag.models import ChatRequest, ChatResponse, HealthResponse, SourceSummary
from nhs_rag.retrieval.embedder import SentenceTransformerEncoder
from nhs_rag.retrieval.service import CorpusUnavailableError, IndexUnavailableError, RagService
from nhs_rag.service import ChatService
from nhs_rag.settings import Settings, get_settings

logger = logging.getLogger("nhs_rag")


def create_app(
    *,
    settings: Settings | None = None,
    rag: RagService | None = None,
    agent: AnswerAgent | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_rag = rag or RagService(
        corpus_dir=runtime_settings.corpus_dir,
        collection_name=runtime_settings.collection_name,
        encoder=SentenceTransformerEncoder(runtime_settings.embedding_model),
        embedding_model=runtime_settings.embedding_model,
        client=QdrantClient(
            url=str(runtime_settings.qdrant_url),
            timeout=runtime_settings.qdrant_timeout_seconds,
            check_compatibility=False,
        ),
    )
    runtime_agent = agent or CodexAnswerAgent(
        model=runtime_settings.codex_model,
        timeout_seconds=runtime_settings.codex_timeout_seconds,
        max_concurrency=runtime_settings.codex_max_concurrency,
        runtime_dir=runtime_settings.codex_runtime_dir,
        enabled=runtime_settings.codex_enabled,
    )
    chat_service = ChatService(
        rag=runtime_rag,
        agent=runtime_agent,
        top_k=runtime_settings.top_k,
        maximum_evidence_chunks=runtime_settings.maximum_evidence_chunks,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not runtime_rag.ready and isinstance(runtime_rag, RagService):
            try:
                await asyncio.to_thread(runtime_rag.load_existing_index)
                logger.info(
                    "NHS Qdrant index loaded: documents=%s chunks=%s",
                    runtime_rag.document_count,
                    runtime_rag.chunk_count,
                )
            except CorpusUnavailableError:
                logger.warning("NHS corpus is absent; readiness will remain false")
            except IndexUnavailableError as error:
                logger.warning("NHS Qdrant index is unavailable: %s", error)
            except Exception:
                logger.exception("NHS Qdrant index validation failed")
        try:
            yield
        finally:
            if isinstance(runtime_rag, RagService):
                runtime_rag.close()

    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        description=(
            "Research prototype for retrieving and synthesising reviewed NHS symptom guidance."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.rag = runtime_rag
    app.state.agent = runtime_agent
    app.state.settings = runtime_settings

    @app.get("/api/v1/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return _health(runtime_rag, runtime_agent, runtime_settings)

    @app.get("/api/v1/health/ready", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        response = _health(runtime_rag, runtime_agent, runtime_settings)
        if not runtime_rag.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The NHS corpus or standalone Qdrant index is not ready.",
            )
        return response

    @app.get("/api/v1/sources", response_model=list[SourceSummary])
    async def sources() -> list[SourceSummary]:
        if not runtime_rag.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Run the NHS ingestion and Qdrant indexing commands, then restart the API.",
            )
        return runtime_rag.source_summaries()

    @app.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        del request  # Explicitly avoid logging or retaining symptom text.
        if not runtime_rag.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The standalone Qdrant index is not ready. Re-index and restart the API.",
            )
        return await chat_service.answer(payload)

    return app


def _health(rag: RagService, agent: AnswerAgent, settings: Settings) -> HealthResponse:
    return HealthResponse(
        status="ok" if rag.ready else "not_ready",
        documents=rag.document_count,
        chunks=rag.chunk_count,
        agent="codex" if agent.enabled else "retrieval_only",
        embedding_model=settings.embedding_model,
    )


app = create_app()
