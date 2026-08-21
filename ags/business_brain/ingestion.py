from __future__ import annotations

import hashlib

from .chunking import chunk_text
from .ports import EmbeddingProvider, KnowledgeLoader, KnowledgeRepository


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
        loaders: list[KnowledgeLoader],
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider
        self.loaders = {loader.source_type: loader for loader in loaders}

    def ingest(self, *, business_id: str, source_type: str, value: str, title: str | None = None) -> dict:
        try:
            loader = self.loaders[source_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported knowledge source type: {source_type}") from exc
        document = loader.load(value, title)
        chunks = chunk_text(document.text)
        if not chunks:
            raise ValueError("Knowledge source did not produce any readable chunks.")
        embeddings = self.embedding_provider.embed(chunks)
        digest = hashlib.sha256(document.text.encode("utf-8")).hexdigest()
        return self.repository.create_source_with_document_and_chunks(
            business_id=business_id,
            source_type=source_type,
            title=document.title,
            source_uri=document.source_uri,
            raw_content=value if source_type == "manual" else document.text,
            normalized_text=document.text,
            content_hash=digest,
            chunks=chunks,
            embeddings=embeddings,
            metadata=document.metadata,
        )
