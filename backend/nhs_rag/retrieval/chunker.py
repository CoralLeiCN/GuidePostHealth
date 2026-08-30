from __future__ import annotations

import hashlib
import uuid

from nhs_rag.models import GuideDocument, RetrievedChunk

CHUNK_NAMESPACE = uuid.UUID("de92c4e0-5133-4627-93ec-25fd87bc95d2")


def _windowed_words(text: str, *, size: int = 180, overlap: int = 28) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text]
    chunks: list[str] = []
    step = size - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size])
        if chunk:
            chunks.append(chunk)
        if start + size >= len(words):
            break
    return chunks


def chunk_document(document: GuideDocument) -> list[RetrievedChunk]:
    canonical_url = str(document.canonical_url)
    document_id = hashlib.sha256(canonical_url.encode()).hexdigest()[:20]
    chunks: list[RetrievedChunk] = []
    for section_index, section in enumerate(document.sections):
        for chunk_index, text in enumerate(_windowed_words(section.text)):
            identity = (
                f"{canonical_url}|{section_index}|{section.heading}|{chunk_index}|"
                f"{hashlib.sha256(text.encode()).hexdigest()}"
            )
            chunks.append(
                RetrievedChunk(
                    id=str(uuid.uuid5(CHUNK_NAMESPACE, identity)),
                    document_id=document_id,
                    title=document.title,
                    heading=section.heading,
                    text=text,
                    url=document.canonical_url,
                    fetched_at=document.fetched_at,
                    urgency=section.urgency,
                )
            )
    return chunks
