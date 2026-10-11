"""SQLite persistence: blocklist and call log."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS blocklist (
  number TEXT PRIMARY KEY,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calls (
  call_sid TEXT PRIMARY KEY,
  caller TEXT,
  line TEXT,
  mode TEXT,
  outcome TEXT,
  details TEXT,
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def is_blocked(self, number: str | None) -> bool:
        if not number:
            return False
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM blocklist WHERE number=?", (number,)).fetchone()
        return row is not None

    def block(self, number: str, reason: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO blocklist(number, reason, created_at) VALUES (?,?,?)",
                (number, reason, _now()),
            )

    def unblock(self, number: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM blocklist WHERE number=?", (number,))

    def blocklist(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self._conn.execute("SELECT number FROM blocklist ORDER BY number")]

    def log_call(self, call_sid: str, caller: str | None, line: str, mode: str, outcome: str, details: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?)",
                (call_sid, caller, line, mode, outcome, json.dumps(details, ensure_ascii=False), _now()),
            )
