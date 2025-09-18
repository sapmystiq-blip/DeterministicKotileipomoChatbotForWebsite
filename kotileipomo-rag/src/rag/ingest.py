from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .config import RAG_KB_DIR
from .tokenize import normalize


@dataclass
class Doc:
    id: str
    text: str
    meta: Dict[str, str]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_kb_docs(kb_root: Optional[str] = None) -> List[Doc]:
    """Flatten multilingual FAQ and deprecated Q&A into docs."""
    root = Path(kb_root or RAG_KB_DIR)
    docs: List[Doc] = []

    # FAQ: multilingual q/a
    faq = _read_json(root / "faq.json") or []
    if isinstance(faq, list):
        for i, row in enumerate(faq):
            q = row.get("q") or {}
            a = row.get("a") or {}
            tags = row.get("tags") or []
            for lang in ("fi","sv","en"):
                ql = (q.get(lang) or "").strip()
                al = (a.get(lang) or "").strip()
                if not ql or not al:
                    continue
                text = f"Q: {ql}\nA: {al}"
                docs.append(Doc(
                    id=f"faq:{i}:{lang}",
                    text=text,
                    meta={"source":"faq.json","lang":lang,"section":"faq","tags":" ".join(tags)}
                ))

    # Deprecated Q&A style files
    dep_dir = root / "deprecated"
    for f in sorted(dep_dir.glob("*.json")):
        data = _read_json(f) or []
        if not isinstance(data, list):
            continue
        for i, row in enumerate(data):
            q = (row.get("question") or "").strip()
            a = (row.get("answer") or "").strip()
            if not q or not a:
                continue
            docs.append(Doc(
                id=f"deprecated:{f.name}:{i}",
                text=f"Q: {q}\nA: {a}",
                meta={"source":f"deprecated/{f.name}","lang":"en","section":"deprecated"}
            ))

    return docs


def chunk_docs(docs: List[Doc], max_chars: int = 1600, overlap: int = 160) -> List[Doc]:
    out: List[Doc] = []
    for d in docs:
        t = d.text
        if len(t) <= max_chars:
            out.append(d)
            continue
        start = 0
        idx = 0
        while start < len(t):
            end = min(len(t), start + max_chars)
            chunk = t[start:end]
            out.append(Doc(
                id=f"{d.id}#c{idx}",
                text=chunk,
                meta={**d.meta, "parent": d.id}
            ))
            if end == len(t):
                break
            start = end - overlap
            idx += 1
    return out

