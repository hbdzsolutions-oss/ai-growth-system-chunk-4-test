from __future__ import annotations

import hashlib
import math
import re

from ags.business_brain.ports import EmbeddingProvider


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding adapter for the first foundation release.

    It avoids coupling Business Brain to an external embedding vendor. It is not
    presented as the final semantic model; the EmbeddingProvider port makes a
    production embedding model replaceable without changing ingestion/retrieval.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return "local-hash"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
