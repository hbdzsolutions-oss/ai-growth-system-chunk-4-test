from __future__ import annotations


def chunk_text(text: str, *, max_chars: int = 900, overlap_chars: int = 120) -> list[str]:
    """Small deterministic chunker with paragraph preference and bounded overlap.

    It is intentionally provider-neutral. Chunk shape can evolve without changing
    loaders, storage, retrievers, or Agent Core contracts.
    """
    cleaned = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()
    if not cleaned:
        return []

    paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(len(paragraph), start + max_chars)
                piece = paragraph[start:end].strip()
                if piece:
                    chunks.append(piece)
                if end >= len(paragraph):
                    break
                start = max(start + 1, end - overlap_chars)
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.strip())
            tail = current[-overlap_chars:].strip() if overlap_chars else ""
            current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    if current.strip():
        chunks.append(current.strip())

    return chunks
