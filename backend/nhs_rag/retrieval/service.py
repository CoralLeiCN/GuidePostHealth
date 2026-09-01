from __future__ import annotations

import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from nhs_rag.models import GuideDocument, RetrievedChunk, SourceSummary
from nhs_rag.retrieval.chunker import chunk_document
from nhs_rag.retrieval.embedder import Encoder


class CorpusUnavailableError(RuntimeError):
    pass


class RagService:
    """Own the process-local embedding model and in-memory Qdrant collection."""

    def __init__(
        self,
        *,
        corpus_dir: Path,
        collection_name: str,
        encoder: Encoder,
        client: QdrantClient | None = None,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.collection_name = collection_name
        self.encoder = encoder
        self.client = client or QdrantClient(":memory:")
        self.documents: list[GuideDocument] = []
        self.chunks: list[RetrievedChunk] = []
        self.ready = False

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def index_corpus(self) -> None:
        documents: list[GuideDocument] = []
        for path in sorted(self.corpus_dir.glob("*.json")):
            try:
                documents.append(GuideDocument.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        if not documents:
            raise CorpusUnavailableError(
                "No parsed NHS guides were found. Run the ingestion command first."
            )

        chunks = [chunk for document in documents for chunk in chunk_document(document)]
        texts = [f"{chunk.title}\n{chunk.heading}\n{chunk.text}" for chunk in chunks]
        vectors = self.encoder.encode(texts)
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding model returned an unexpected number of vectors")

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.encoder.dimension, distance=Distance.COSINE),
        )
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    **chunk.model_dump(mode="json", exclude={"score"}),
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        for start in range(0, len(points), 128):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start : start + 128],
                wait=True,
            )

        self.documents = documents
        self.chunks = chunks
        self.ready = True

    def search(self, query: str, *, top_k: int = 6, maximum: int = 9) -> list[RetrievedChunk]:
        if not self.ready:
            raise CorpusUnavailableError("The NHS guide index is not ready")
        query_vector = self.encoder.encode([query])[0]
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        retrieved: list[RetrievedChunk] = []
        for point in result.points:
            if not point.payload:
                continue
            retrieved.append(
                RetrievedChunk.model_validate({**point.payload, "score": float(point.score)})
            )

        # Dense retrieval can miss the urgent card next to an otherwise relevant section.
        matched_documents = {chunk.document_id for chunk in retrieved[:3]}
        seen = {chunk.id for chunk in retrieved}
        safety_chunks = [
            chunk
            for chunk in self.chunks
            if chunk.document_id in matched_documents
            and chunk.urgency in {"emergency", "urgent"}
            and chunk.id not in seen
        ]
        retrieved.extend(safety_chunks)
        return retrieved[:maximum]

    def source_summaries(self) -> list[SourceSummary]:
        return [
            SourceSummary(
                title=document.title,
                url=document.canonical_url,
                fetched_at=document.fetched_at,
                last_reviewed=document.last_reviewed,
                sections=len(document.sections),
            )
            for document in self.documents
        ]
