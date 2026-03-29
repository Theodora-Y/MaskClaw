"""SQLite-backed Chat History storage with per-user conversation support.

Tables:
- conversations: 每个会话的元信息
- messages: 每条消息的内容
"""

from __future__ import annotations

import json
import sqlite3
import time as time_module
from pathlib import Path
from typing import Any, Dict, List, Optional

import fcntl


class ChatHistoryDB:
    """Chat history data layer — one database per user, keyed by user_id."""

    def __init__(self, db_path: str = "memory/chat_history.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.db_path.with_suffix(self.db_path.suffix + ".lock")
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _with_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return lock_file

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    def init_db(self) -> None:
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id          TEXT PRIMARY KEY,
                        user_id     TEXT NOT NULL,
                        title       TEXT NOT NULL DEFAULT '新建任务',
                        created_at  INTEGER NOT NULL,
                        updated_at  INTEGER NOT NULL,
                        UNIQUE(user_id, id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id              TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        user_id         TEXT NOT NULL,
                        role            TEXT NOT NULL,
                        content         TEXT NOT NULL,
                        ts              INTEGER NOT NULL,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                        UNIQUE(conversation_id, id)
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conv_user
                        ON conversations(user_id, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_msg_conv
                        ON messages(conversation_id, ts ASC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_msg_user
                        ON messages(user_id, ts DESC)
                """)
                conn.commit()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def list_conversations(
        self, user_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_conversation(
        self, user_id: str, conv_id: str
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, title, created_at, updated_at
                FROM conversations
                WHERE id = ? AND user_id = ?
                """,
                (conv_id, user_id),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def create_conversation(
        self, user_id: str, conv_id: str, title: str, created_at: int
    ) -> bool:
        now = int(time_module.time())
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conv_id, user_id, title, created_at, now),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_conversation(
        self, user_id: str, conv_id: str, title: str
    ) -> bool:
        now = int(time_module.time())
        cur = None
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (title, now, conv_id, user_id),
            )
            conn.commit()
        return (cur.rowcount or 0) > 0

    def touch_conversation(self, conv_id: str) -> None:
        """更新 conversation 的 updated_at 时间戳。"""
        now = int(time_module.time())
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )
            conn.commit()

    def delete_conversation(self, user_id: str, conv_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                DELETE FROM conversations WHERE id = ? AND user_id = ?
                """,
                (conv_id, user_id),
            )
            conn.commit()
        return (cur.rowcount or 0) > 0

    def get_messages(
        self, user_id: str, conv_id: str
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM conversations WHERE id = ? AND user_id = ?
                """,
                (conv_id, user_id),
            ).fetchone()
            if not row:
                return []

            rows = conn.execute(
                """
                SELECT id, conversation_id, user_id, role, content, ts
                FROM messages
                WHERE conversation_id = ?
                ORDER BY ts ASC
                """,
                (conv_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def add_message(
        self,
        conv_id: str,
        user_id: str,
        msg_id: str,
        role: str,
        content: str,
        ts: int,
    ) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, user_id, role, content, ts)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (msg_id, conv_id, user_id, role, content, ts),
                )
                conn.commit()
            self.touch_conversation(conv_id)
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_all_for_user(self, user_id: str) -> int:
        """删除用户所有聊天记录（用于测试或账号注销）。"""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM conversations WHERE user_id = ?", (user_id,)
            )
            conn.commit()
        return cur.rowcount or 0
