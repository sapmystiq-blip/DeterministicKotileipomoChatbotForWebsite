from __future__ import annotations

from typing import List, Tuple
from difflib import SequenceMatcher

from .ingest import Doc
from .index_bm25 import BM25Index
from .index_embeddings import EmbIndex


class Retriever:
    def __init__(self, bm25: BM25Index, emb: EmbIndex | None = None):
        self.bm25 = bm25
        self.emb = emb or EmbIndex()

    def retrieve(self, query: str, lang: str, top_k: int = 8) -> List[Tuple[float, Doc]]:
        # Hybrid union then simple re-rank by normalized similarity to metadata hints
        bm = self.bm25.search(query, top_k=20)
        ve = self.emb.search(query, top_k=20) if getattr(self.emb, "ready", False) else []
        pool = {d.id: (s, d) for s, d in bm}
        for s, d in ve:
            pool[d.id] = max(pool.get(d.id, (s, d)), (s, d))
        scored = list(pool.values())
        # Light language preference and fuzzy tie-break
        qn = query.lower()
        rescored: List[Tuple[float, Doc]] = []
        for s, d in scored:
            bonus = 0.0
            if d.meta.get("lang") == lang:
                bonus += 0.1
            # prefer FAQ first
            if d.meta.get("source") == "faq.json":
                bonus += 0.05
            sim = SequenceMatcher(None, (d.meta.get("tags") or "") + d.id, qn).ratio()
            rescored.append((s + bonus + 0.1 * sim, d))
        rescored.sort(key=lambda x: x[0], reverse=True)
        return rescored[:top_k]

