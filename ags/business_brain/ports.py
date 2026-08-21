from __future__ import annotations

from abc import ABC, abstractmethod

from .models import KnowledgeItem, LoadedDocument


class KnowledgeLoader(ABC):
    source_type: str

    @abstractmethod
    def load(self, value: str, title: str | None = None) -> LoadedDocument:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def dimensions(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class KnowledgeRepository(ABC):
    @abstractmethod
    def create_source_with_document_and_chunks(
        self,
        *,
        business_id: str,
        source_type: str,
        title: str,
        source_uri: str | None,
        raw_content: str,
        normalized_text: str,
        content_hash: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, str],
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_sources(self, business_id: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def list_chunks(self, business_id: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def delete_source(self, business_id: str, source_id: str) -> None:
        raise NotImplementedError


class KnowledgeRetriever(ABC):
    @abstractmethod
    def retrieve(self, business_id: str, query: str, limit: int = 5) -> list[KnowledgeItem]:
        raise NotImplementedError
