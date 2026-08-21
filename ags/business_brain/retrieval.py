from __future__ import annotations

import math

from .models import KnowledgeItem
from .ports import EmbeddingProvider, KnowledgeRepository, KnowledgeRetriever


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class RepositoryKnowledgeRetriever(KnowledgeRetriever):
    """Portable baseline retriever.

    Search is deliberately behind KnowledgeRetriever. The current SQL-backed
    implementation ranks stored vectors in-process; a pgvector/Qdrant/etc.
    adapter can replace this without touching Agent Core or chat orchestration.
    """

    def __init__(self, repository: KnowledgeRepository, embedding_provider: EmbeddingProvider) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider

    def retrieve(self, business_id: str, query: str, limit: int = 5) -> list[KnowledgeItem]:
        rows = self.repository.list_chunks(business_id)
        if not rows:
            return []
        query_vector = self.embedding_provider.embed([query])[0]
        ranked: list[tuple[float, dict]] = []
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        for row in rows:
            vector_score = _cosine(query_vector, row["embedding"])
            content_lower = row["content"].lower()
            keyword_hits = sum(1 for term in query_terms if term.strip("?.,!:") in content_lower)
            keyword_bonus = min(0.25, keyword_hits * 0.05)
            ranked.append((vector_score + keyword_bonus, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeItem(
                chunk_id=row["id"],
                content=row["content"],
                score=score,
                source_title=row["source_title"],
                source_type=row["source_type"],
                source_uri=row.get("source_uri"),
            )
            for score, row in ranked[:limit]
        ]
