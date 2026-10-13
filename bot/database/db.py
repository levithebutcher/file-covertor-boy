"""
Local SQLite database manager for Telegram Media Suite.
Completely standalone, persistent, zero-network, and lightning fast.
"""

import sqlite3
import asyncio
from pathlib import Path
from typing import Any, List, Optional, Tuple

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"


class SQLiteManager:
    """Thread-safe async wrapper around standard Python sqlite3."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Create tables if not already present."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT DEFAULT 'whitelisted',
                    mode TEXT DEFAULT 'convert',
                    added_by INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)
            conn.commit()

    def execute_sync(self, query: str, params: Tuple = ()) -> int:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.rowcount

    def fetchone_sync(self, query: str, params: Tuple = ()) -> Optional[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def fetchall_sync(self, query: str, params: Tuple = ()) -> List[dict]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    async def execute(self, query: str, params: Tuple = ()) -> int:
        return await asyncio.to_thread(self.execute_sync, query, params)

    async def fetchone(self, query: str, params: Tuple = ()) -> Optional[dict]:
        return await asyncio.to_thread(self.fetchone_sync, query, params)

    async def fetchall(self, query: str, params: Tuple = ()) -> List[dict]:
        return await asyncio.to_thread(self.fetchall_sync, query, params)


db_manager = SQLiteManager()
