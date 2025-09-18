kotileipomo-rag — Hybrid RAG for Kotileipomo

Overview

- Goal: ChatGPT-like answers grounded in your knowledge base and site.
- Scope: Retrieval and answer composition only. Does not change your existing ordering/menu display logic.
- Architecture: Hybrid BM25 + embeddings (optional) → re-rank (optional) → grounded answer composer.

Structure

- src/rag/config.py: Paths, feature flags, models.
- src/rag/tokenize.py: Normalization, diacritic folding, light FI/SV/EN stemming.
- src/rag/ingest.py: Flatten KB (faq, deprecated) and site stubs into a document corpus.
- src/rag/index_bm25.py: Simple BM25 index build/query.
- src/rag/index_embeddings.py: Embedding index stubs (optional; falls back to BM25).
- src/rag/retrieve.py: Hybrid retrieval union + simple re-rank.
- src/rag/generate.py: Grounded answer composer (concise, multilingual).
- scripts/build_index.py: Build the index artifacts.
- scripts/query.py: CLI to query the index.

Usage (local, no network)

1) Build index
   - python scripts/build_index.py

2) Query
   - python scripts/query.py "Käytättekö ympäristöystävällisiä pakkauksia?" --lang fi

Feature Flags

- RAG_EMBEDDINGS=0/1: Enable embeddings index (requires model + network)
- RAG_DATA_DIR: Output dir for indexes (default: data/)
- RAG_KB_DIR: Path to KB root (default: ../backend/knowledgebase)

Notes

- If embeddings are disabled or unavailable, the retriever uses BM25-only.
- This repository is standalone and does not modify your current app. You can later integrate via a small API bridge.

