import os
from pathlib import Path

# Resolve the monorepo root (…/KotileipomoChatbotForWebsite) from kotileipomo-rag/src/rag/
_HERE = Path(__file__).resolve()
_CAND_ROOTS = [
    _HERE.parents[3],  # …/KotileipomoChatbotForWebsite
    _HERE.parents[2],  # fallback: …/kotileipomo-rag
]
REPO_ROOT = next((p for p in _CAND_ROOTS if (p / "backend").exists()), _HERE.parents[3])
DEFAULT_KB_DIR = (REPO_ROOT / "backend" / "knowledgebase").as_posix()

RAG_KB_DIR = os.getenv("RAG_KB_DIR", DEFAULT_KB_DIR)
RAG_DATA_DIR = os.getenv("RAG_DATA_DIR", (REPO_ROOT / "kotileipomo-rag" / "data").as_posix())

RAG_EMBEDDINGS = os.getenv("RAG_EMBEDDINGS", "0") in {"1", "true", "on", "yes"}
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-large")

Path(RAG_DATA_DIR).mkdir(parents=True, exist_ok=True)
