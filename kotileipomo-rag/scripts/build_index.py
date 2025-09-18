#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure ../src is on sys.path for `import rag` without PYTHONPATH
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rag.config import RAG_DATA_DIR
from rag.ingest import load_kb_docs, chunk_docs
from rag.index_bm25 import BM25Index
from rag.index_embeddings import EmbIndex


def main():
    docs = load_kb_docs()
    docs = chunk_docs(docs)
    print(f"Loaded {len(docs)} docs")

    # Save a corpus manifest
    out_dir = Path(RAG_DATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "corpus.jsonl").write_text(
        "\n".join(json.dumps({"id": d.id, "meta": d.meta}) for d in docs),
        encoding="utf-8"
    )

    # Build BM25
    bm25 = BM25Index(docs)
    # Persist minimal state (we rely on rebuild in-memory for simplicity)
    (out_dir / "bm25.info").write_text(
        json.dumps({"N": bm25.N, "avg_len": bm25.avg_len, "vocab": len(bm25.df)}),
        encoding="utf-8"
    )
    print("BM25 index built.")

    # Embeddings placeholder
    emb = EmbIndex()
    emb.build(docs)
    print("Embeddings index: disabled (stub).")


if __name__ == "__main__":
    main()
