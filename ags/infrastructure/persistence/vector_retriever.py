from __future__ import annotations

from sqlalchemy import text

from ags.business_brain.models import KnowledgeItem
from ags.business_brain.ports import EmbeddingProvider, KnowledgeRepository, KnowledgeRetriever
from ags.business_brain.retrieval import RepositoryKnowledgeRetriever

from .database import Database


class SqlKnowledgeRetriever(KnowledgeRetriever):
    """Database-aware retrieval adapter.

    PostgreSQL uses pgvector cosine search. SQLite/local tests transparently use
    the portable repository fallback. Both satisfy the same KnowledgeRetriever
    port consumed by the application layer.
    """

    def __init__(
        self,
        database: Database,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.database = database
        self.embedding_provider = embedding_provider
        self.fallback = RepositoryKnowledgeRetriever(repository, embedding_provider)

    def retrieve(self, business_id: str, query: str, limit: int = 5) -> list[KnowledgeItem]:
        if self.database.engine.dialect.name != "postgresql":
            return self.fallback.retrieve(business_id, query, limit)

        vector = self.embedding_provider.embed([query])[0]
        vector_literal = "[" + ",".join(f"{value:.12g}" for value in vector) + "]"
        sql = text(
            """
            SELECT
                kc.id,
                kc.content,
                ks.title AS source_title,
                ks.source_type,
                ks.source_uri,
                1 - (kc.embedding_vector <=> CAST(:query_vector AS vector)) AS score
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kd.id = kc.document_id
            JOIN knowledge_sources ks ON ks.id = kd.source_id
            WHERE kc.business_id = :business_id
              AND ks.status = 'ready'
              AND kc.embedding_vector IS NOT NULL
            ORDER BY kc.embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        )
        with self.database.session_factory() as session:
            rows = session.execute(
                sql,
                {
                    "query_vector": vector_literal,
                    "business_id": business_id,
                    "limit": limit,
                },
            ).mappings()
            return [
                KnowledgeItem(
                    chunk_id=row["id"],
                    content=row["content"],
                    score=float(row["score"] or 0.0),
                    source_title=row["source_title"],
                    source_type=row["source_type"],
                    source_uri=row["source_uri"],
                )
                for row in rows
            ]
