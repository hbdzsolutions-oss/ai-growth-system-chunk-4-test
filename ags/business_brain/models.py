from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoadedDocument:
    title: str
    text: str
    source_uri: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeItem:
    chunk_id: str
    content: str
    score: float
    source_title: str
    source_type: str
    source_uri: str | None = None
