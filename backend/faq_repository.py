from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .kb_models import FaqItem

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
FAQ_TREE_FILE = REPO_ROOT / "docs" / "faq_tree.json"
FAQ_ENTRIES_FILE = REPO_ROOT / "docs" / "faq_entries.json"
FAQ_META_FILE = REPO_ROOT / "docs" / "faq_meta.json"
FAQ_KB_FILE = HERE / "knowledgebase" / "faq.json"


@dataclass
class EntryRecord:
    id: str
    category_path: Tuple[str, ...]
    sources: List[str]
    order: int


class FaqRepository:
    _instance: Optional["FaqRepository"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.version: str = "0"
        self._tree: List[dict] = []
        self._entry_records: List[EntryRecord] = []
        self._faq_items: List[FaqItem] = []
        self._items_by_path: Dict[Tuple[str, ...], List[FaqItem]] = {}
        self._records_by_question: Dict[str, EntryRecord] = {}
        self._node_counts: Dict[Tuple[str, ...], int] = {}
        self._tree_mtime: float = 0.0
        self._entries_mtime: float = 0.0
        self._meta_mtime: float = 0.0
        self._kb_mtime: float = 0.0
        self._loaded = False

    @classmethod
    def instance(cls) -> "FaqRepository":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            repo = cls._instance
        repo.ensure_latest()
        return repo

    def ensure_latest(self) -> None:
        tree_mtime = FAQ_TREE_FILE.stat().st_mtime if FAQ_TREE_FILE.exists() else 0.0
        entries_mtime = FAQ_ENTRIES_FILE.stat().st_mtime if FAQ_ENTRIES_FILE.exists() else 0.0
        meta_mtime = FAQ_META_FILE.stat().st_mtime if FAQ_META_FILE.exists() else 0.0
        kb_mtime = FAQ_KB_FILE.stat().st_mtime if FAQ_KB_FILE.exists() else 0.0
        if not self._loaded or any([
            tree_mtime != self._tree_mtime,
            entries_mtime != self._entries_mtime,
            meta_mtime != self._meta_mtime,
            kb_mtime != self._kb_mtime,
        ]):
            self.reload()

    def reload(self) -> None:
        tree = self._read_json(FAQ_TREE_FILE, [])
        entries = self._read_json(FAQ_ENTRIES_FILE, [])
        meta = self._read_json(FAQ_META_FILE, {})
        kb_items_raw = self._read_json(FAQ_KB_FILE, [])

        faq_items: List[FaqItem] = []
        items_by_path: Dict[Tuple[str, ...], List[FaqItem]] = {}
        for row in kb_items_raw:
            try:
                faq = FaqItem.parse_obj(row)
            except Exception:
                continue
            faq_items.append(faq)
            path = tuple(faq.category_path or [])
            if path:
                items_by_path.setdefault(path, []).append(faq)

        entry_records: List[EntryRecord] = []
        records_by_question: Dict[str, EntryRecord] = {}
        node_counts: Dict[Tuple[str, ...], int] = {}
        for idx, entry in enumerate(entries):
            q = entry.get("question", {}).get("fi")
            path = tuple(entry.get("category_path") or [])
            if not q or not path:
                continue
            record = EntryRecord(
                id=str(entry.get("id") or idx),
                category_path=path,
                sources=[s.strip() for s in entry.get("sources", []) if s.strip()],
                order=idx,
            )
            entry_records.append(record)
            records_by_question[q] = record
            node_counts[path] = node_counts.get(path, 0) + 1
            # bubble counts up
            for depth in range(1, len(path)):
                prefix = path[:depth]
                node_counts[prefix] = node_counts.get(prefix, 0) + 1

        # Sort items within each path by the order defined in entries; fallback to question text
        ordered_by_path: Dict[Tuple[str, ...], List[FaqItem]] = {}
        for path, items in items_by_path.items():
            def sort_key(item: FaqItem) -> Tuple[int, str]:
                record = records_by_question.get(item.q.get("fi", ""))
                return (record.order if record else 10_000_000, item.q.get("fi", ""))
            ordered_by_path[path] = sorted(items, key=sort_key)

        self._tree = tree
        self._entry_records = entry_records
        self._faq_items = faq_items
        self._items_by_path = ordered_by_path
        self._records_by_question = records_by_question
        self._node_counts = node_counts
        self.version = str(meta.get("faq_version") or meta.get("version") or "1")
        self._tree_mtime = FAQ_TREE_FILE.stat().st_mtime if FAQ_TREE_FILE.exists() else 0.0
        self._entries_mtime = FAQ_ENTRIES_FILE.stat().st_mtime if FAQ_ENTRIES_FILE.exists() else 0.0
        self._meta_mtime = FAQ_META_FILE.stat().st_mtime if FAQ_META_FILE.exists() else 0.0
        self._kb_mtime = FAQ_KB_FILE.stat().st_mtime if FAQ_KB_FILE.exists() else 0.0
        self._loaded = True

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _localize_label(self, label: Dict[str, str], lang: Optional[str]) -> Dict[str, str]:
        if not label:
            return {"value": ""}
        selected = label.get(lang or "") or label.get("fi") or next(iter(label.values()))
        return {"value": selected, "all": label}

    def tree(self, lang: Optional[str] = None) -> List[dict]:
        def transform(node: dict) -> dict:
            node_path = tuple(node.get("path") or [])
            children = [transform(child) for child in node.get("children", [])]
            data = {
                "id": node.get("id"),
                "path": node.get("path"),
                "label": (node.get("label", {}).get(lang or "") or node.get("label", {}).get("fi") or next(iter((node.get("label") or {}).values()), "")),
                "labels": node.get("label", {}),
                "count": self._node_counts.get(tuple(node_path), 0),
                "children": children,
            }
            return data
        return [transform(node) for node in self._tree]

    def entries_for(self, path: List[str], lang: Optional[str] = None) -> List[dict]:
        key = tuple(path)
        # Collect items for the exact node; if there are no items directly,
        # include items from descendant paths so parent tabs can aggregate
        # grandchildren when the tree hides intermediate nodes.
        items = list(self._items_by_path.get(key, []))
        if not items:
            gathered: List[FaqItem] = []
            for p, lst in self._items_by_path.items():
                if len(p) > len(key) and p[: len(key)] == key:
                    gathered.extend(lst)
            items = gathered
        results: List[dict] = []
        # Sort combined items by the global entry order when available
        def _order_of(it: FaqItem) -> int:
            rec = self._records_by_question.get(it.q.get("fi", ""))
            return rec.order if rec else 10_000_000
        items = sorted(items, key=lambda it: (_order_of(it), it.q.get("fi", "")))

        for item in items:
            question = item.text_for(lang or "", "q")
            answer = item.text_for(lang or "", "a")
            sources = []
            record = self._records_by_question.get(item.q.get("fi", ""))
            if record:
                sources = record.sources
                entry_id = record.id
            else:
                entry_id = _slugify(item.q.get("fi", question))
            results.append({
                "id": entry_id,
                "question": item.q,
                "answer": item.a,
                "lang": lang or "",
                "default_answer": answer,
                "default_question": question,
                "sources": sources,
            })
        return results


@lru_cache(maxsize=1)
def get_faq_repository() -> FaqRepository:
    return FaqRepository.instance()


def _slugify(text: str) -> str:
    import re
    import unicodedata

    if not text:
        return "entry"
    normalized = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", stripped).strip("-")
    return slug or "entry"
