from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from nhs_rag.models import GuideDocument, RetrievedChunk, SourceSummary
from nhs_rag.retrieval.chunker import chunk_document
from nhs_rag.retrieval.embedder import Encoder


class CorpusUnavailableError(RuntimeError):
    pass


class IndexUnavailableError(RuntimeError):
    pass


INDEX_SCHEMA_VERSION = 1


class RagService:
    """Index and retrieve the local corpus through a standalone Qdrant server."""

    def __init__(
        self,
        *,
        corpus_dir: Path,
        collection_name: str,
        encoder: Encoder,
        embedding_model: str,
        client: QdrantClient,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.collection_name = collection_name
        self.encoder = encoder
        self.embedding_model = embedding_model
        self.client = client
        self.documents: list[GuideDocument] = []
        self.chunks: list[RetrievedChunk] = []
        self.ready = False

    def close(self) -> None:
        self.client.close()

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def _read_corpus(self) -> tuple[list[GuideDocument], list[RetrievedChunk]]:
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
        return documents, chunks

    def _index_metadata(self, chunks: list[RetrievedChunk]) -> dict[str, object]:
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(chunk.model_dump_json(exclude={"score"}).encode())
            digest.update(b"\n")
        return {
            "guidepost": {
                "schema_version": INDEX_SCHEMA_VERSION,
                "corpus_sha256": digest.hexdigest(),
                "embedding_model": self.embedding_model,
                "vector_size": self.encoder.dimension,
                "chunk_count": len(chunks),
            }
        }

    def load_existing_index(self) -> None:
        """Load local safety metadata and validate the persisted Qdrant collection."""
        self.ready = False
        documents, chunks = self._read_corpus()
        if not self.client.collection_exists(self.collection_name):
            raise IndexUnavailableError(
                f"Qdrant collection {self.collection_name!r} is missing. Run the index command."
            )

        collection = self.client.get_collection(self.collection_name)
        expected_metadata = self._index_metadata(chunks)
        if collection.config.metadata != expected_metadata:
            raise IndexUnavailableError(
                "The Qdrant index does not match this corpus and embedding model. "
                "Run the index command."
            )
        point_count = self.client.count(self.collection_name, exact=True).count
        if point_count != len(chunks):
            raise IndexUnavailableError(
                f"The Qdrant index has {point_count} points; expected {len(chunks)}. "
                "Run the index command."
            )

        self.documents = documents
        self.chunks = chunks
        self.ready = True

    def index_corpus(self) -> None:
        """Explicitly rebuild the standalone Qdrant collection from the local corpus."""
        self.ready = False
        documents, chunks = self._read_corpus()
        metadata = self._index_metadata(chunks)
        texts = [f"{chunk.title}\n{chunk.heading}\n{chunk.text}" for chunk in chunks]
        vectors = self.encoder.encode(texts)
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding model returned an unexpected number of vectors")

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.encoder.dimension, distance=Distance.COSINE),
            metadata=metadata,
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

        point_count = self.client.count(self.collection_name, exact=True).count
        if point_count != len(points):
            raise RuntimeError(
                f"Qdrant stored {point_count} points; expected {len(points)} after indexing"
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
