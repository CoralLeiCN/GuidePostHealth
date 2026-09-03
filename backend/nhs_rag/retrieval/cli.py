from __future__ import annotations

from qdrant_client import QdrantClient

from nhs_rag.retrieval.embedder import SentenceTransformerEncoder
from nhs_rag.retrieval.service import RagService
from nhs_rag.settings import get_settings


def main() -> None:
    settings = get_settings()
    service = RagService(
        corpus_dir=settings.corpus_dir,
        collection_name=settings.collection_name,
        encoder=SentenceTransformerEncoder(settings.embedding_model),
        embedding_model=settings.embedding_model,
        client=QdrantClient(
            url=str(settings.qdrant_url),
            timeout=settings.qdrant_timeout_seconds,
            check_compatibility=False,
        ),
    )
    try:
        service.index_corpus()
        print(
            f"Indexed {service.document_count} documents and {service.chunk_count} chunks "
            f"into Qdrant collection {service.collection_name!r}."
        )
    finally:
        service.close()


if __name__ == "__main__":
    main()
