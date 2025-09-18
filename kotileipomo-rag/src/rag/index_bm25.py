from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Dict, List, Tuple

from .tokenize import tokenize_list
from .ingest import Doc


@dataclass
class BM25Doc:
    id: str
    toks: List[str]
    length: int
    meta: Dict[str, str]
    text: str


class BM25Index:
    def __init__(self, docs: List[Doc]):
        self.docs: List[BM25Doc] = []
        self.df: Counter[str] = Counter()
        for d in docs:
            toks = tokenize_list(d.text)
            dedup = set(toks)
            self.docs.append(BM25Doc(d.id, toks, len(toks), d.meta, d.text))
            for t in dedup:
                self.df[t] += 1
        self.N = len(self.docs)
        self.avg_len = (sum(d.length for d in self.docs) / max(1, self.N)) if self.docs else 0.0

    def _bm25(self, q: List[str], d: BM25Doc) -> float:
        if not d.toks:
            return 0.0
        tf = Counter(d.toks)
        k1, b = 1.4, 0.75
        score = 0.0
        for qt in q:
            df = self.df.get(qt, 0)
            if df == 0:
                continue
            idf = log(1 + (self.N - df + 0.5) / (df + 0.5))
            f = tf.get(qt, 0)
            denom = f + k1 * (1 - b + b * (d.length / (self.avg_len or 1)))
            score += idf * ((f * (k1 + 1)) / (denom or 1))
        return score

    def search(self, query: str, top_k: int = 20) -> List[Tuple[float, Doc]]:
        q = tokenize_list(query)
        scored: List[Tuple[float, Doc]] = []
        for d in self.docs:
            s = self._bm25(q, d)
            if s > 0:
                scored.append((s, Doc(id=d.id, text=d.text, meta=d.meta)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]
