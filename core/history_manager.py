"""
Past-query-experience store.

Every generated (question -> SQL) pair is appended here. The vector store
embeds these questions so future similar questions can retrieve real,
previously-used SQL as few-shot examples for the LLM -- this is how the
system "learns" the house style / common joins over time without retraining.
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import List

import config


class HistoryManager:
    def __init__(self, path: str = None):
        self.path = path or config.QUERY_HISTORY_PATH
        self._lock = threading.Lock()
        self.entries: List[dict] = self._load()

    def _load(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def add_entry(self, question: str, sql: str, tables_used: List[str], feedback: str = "generated") -> dict:
        entry = {
            "id": str(uuid.uuid4())[:8],
            "question": question,
            "sql": sql,
            "tables_used": tables_used,
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.entries.append(entry)
            self._save()
        return entry

    def get_all(self) -> List[dict]:
        return list(self.entries)

    def get_documents_for_index(self) -> List[dict]:
        """Documents keyed by history entry id, text = the question (what we match on)."""
        return [{"id": e["id"], "text": e["question"]} for e in self.entries]

    def get_by_id(self, entry_id: str) -> dict:
        for e in self.entries:
            if e["id"] == entry_id:
                return e
        return None
