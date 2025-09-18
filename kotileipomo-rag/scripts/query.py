#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure ../src is on sys.path for `import rag` without PYTHONPATH
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rag.ingest import load_kb_docs, chunk_docs
from rag.index_bm25 import BM25Index
from rag.index_embeddings import EmbIndex
from rag.retrieve import Retriever
from rag.generate import compose_answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="User query")
    ap.add_argument("--lang", default="fi", choices=["fi","sv","en"])
    args = ap.parse_args()

    docs = chunk_docs(load_kb_docs())
    bm = BM25Index(docs)
    emb = EmbIndex()
    r = Retriever(bm25=bm, emb=emb)
    hits = r.retrieve(args.query, args.lang, top_k=8)
    ans = compose_answer(args.query, hits, args.lang)
    print(ans)


if __name__ == "__main__":
    main()
