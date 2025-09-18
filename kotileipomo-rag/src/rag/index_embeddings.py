from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .ingest import Doc


@dataclass
class EmbIndex:
    ready: bool = False

    def build(self, docs: List[Doc]):
        # Placeholder: wire a multilingual embeddings model here
        self.ready = False

    def search(self, query: str, top_k: int = 20) -> List[Tuple[float, Doc]]:
        # Not available; return empty set to let BM25 carry the load
        return []

