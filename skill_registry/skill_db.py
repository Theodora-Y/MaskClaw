"""SQLite-backed Skill registry with version history support."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import fcntl


class SkillDB:
    """Skill lifecycle data layer.

    Active skills keep file paths in `path`.
    Archived skills have empty path and keep full file contents in DB.
    """

    def __init__(self, db_path: str = "skill_registry/skill_registry.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.db_path.with_suffix(self.db_path.suffix + ".lock")
        self.init_db()

    @staticmethod
    def is_active(path: str) -> bool:
        return bool(path) and ".archive" not in path

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
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS skills (
                      id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id            TEXT    NOT NULL,
                      skill_name         TEXT    NOT NULL,
                      version            TEXT    NOT NULL,
                      path               TEXT    NOT NULL,
                      confidence         REAL,
                      trigger_count      INTEGER DEFAULT 0,
                      content_hash       TEXT,
                      strategy           TEXT,
                      sensitive_field    TEXT,
                      scene              TEXT,
                      rule_text          TEXT,
                      skill_md_content   TEXT,
                      rules_json_content TEXT,
                      created_ts         INTEGER NOT NULL,
                      archived_ts        INTEGER,
                      archived_reason    TEXT,
                      superseded_by      TEXT,
                      UNIQUE(user_id, skill_name, version)
                    )
                    """
                )
                conn.commit()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def add_skill(
        self,
        user_id: str,
        skill_name: str,
        version: str,
        path: str,
        rule_dict: Dict[str, Any],
    ) -> bool:
        skill_dir = Path(path)
        skill_md_path = skill_dir / "SKILL.md"
        rules_json_path = skill_dir / "rules.json"

        skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""
        rules_json_content = rules_json_path.read_text(encoding="utf-8") if rules_json_path.exists() else ""
        content_hash = hashlib.md5((skill_md_content + rules_json_content).encode("utf-8")).hexdigest()

        old_active_path = ""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                exists = conn.execute(
                    """
                    SELECT 1 FROM skills
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (user_id, skill_name, version),
                ).fetchone()
                if exists:
                    return False

                active_row = conn.execute(
                    """
                    SELECT version FROM skills
                    WHERE user_id = ? AND skill_name = ? AND path != ''
                    ORDER BY created_ts DESC
                    LIMIT 1
                    """,
                    (user_id, skill_name),
                ).fetchone()

                if active_row:
                    old_active_version = str(active_row["version"])
                    old_row = conn.execute(
                        """
                        SELECT path FROM skills
                        WHERE user_id = ? AND skill_name = ? AND version = ?
                        """,
                        (user_id, skill_name, old_active_version),
                    ).fetchone()
                    old_active_path = str((old_row["path"] if old_row else "") or "")
                    conn.execute(
                        """
                        UPDATE skills
                        SET path = '', archived_ts = ?, archived_reason = ?, superseded_by = ?
                        WHERE user_id = ? AND skill_name = ? AND version = ?
                        """,
                        (int(time.time()), "superseded", version, user_id, skill_name, old_active_version),
                    )

                now_ts = int(time.time())
                conn.execute(
                    """
                    INSERT INTO skills (
                      user_id, skill_name, version, path,
                      confidence, trigger_count, content_hash,
                      strategy, sensitive_field, scene, rule_text,
                      skill_md_content, rules_json_content,
                      created_ts, archived_ts, archived_reason, superseded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                    """,
                    (
                        user_id,
                        skill_name,
                        version,
                        str(path),
                        float(rule_dict.get("confidence", 0.0)),
                        int(rule_dict.get("trigger_count", 0)),
                        content_hash,
                        str(rule_dict.get("strategy", "")),
                        str(rule_dict.get("sensitive_field", "")),
                        str(rule_dict.get("scene", "")),
                        str(rule_dict.get("rule_text", "")),
                        skill_md_content,
                        rules_json_content,
                        now_ts,
                    ),
                )
                conn.commit()
            if old_active_path:
                old_dir = Path(old_active_path)
                if old_dir.exists() and old_dir.is_dir():
                    for p in sorted(old_dir.rglob("*"), reverse=True):
                        if p.is_file():
                            p.unlink(missing_ok=True)
                        elif p.is_dir():
                            p.rmdir()
                    old_dir.rmdir()
            return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def archive_skill(
        self,
        user_id: str,
        skill_name: str,
        version: str,
        reason: str,
        superseded_by: Optional[str] = None,
        delete_files: bool = False,
    ) -> bool:
        lock_file = self._with_lock()
        old_path = ""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT path FROM skills
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (user_id, skill_name, version),
                ).fetchone()
                if not row:
                    return False
                old_path = str(row["path"] or "")
                if not old_path:
                    return False

                conn.execute(
                    """
                    UPDATE skills
                    SET path = '',
                        archived_ts = ?,
                        archived_reason = ?,
                        superseded_by = ?
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (int(time.time()), reason, superseded_by, user_id, skill_name, version),
                )
                conn.commit()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

        if delete_files and old_path:
            old_dir = Path(old_path)
            if old_dir.exists() and old_dir.is_dir():
                for p in sorted(old_dir.rglob("*"), reverse=True):
                    if p.is_file():
                        p.unlink(missing_ok=True)
                    elif p.is_dir():
                        p.rmdir()
                old_dir.rmdir()

        return True

    def restore_skill(
        self,
        user_id: str,
        skill_name: str,
        version: str,
        base_dir: str,
    ) -> bool:
        old_active_path = ""
        lock_file = self._with_lock()
        restored_path = ""
        skill_md_content = ""
        rules_json_content = ""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM skills
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (user_id, skill_name, version),
                ).fetchone()
                if not row:
                    return False
                if str(row["path"] or ""):
                    return False

                active = conn.execute(
                    """
                    SELECT version FROM skills
                    WHERE user_id = ? AND skill_name = ? AND path != ''
                    ORDER BY created_ts DESC
                    LIMIT 1
                    """,
                    (user_id, skill_name),
                ).fetchone()

                if active:
                    old_active_version = str(active["version"])
                    old_row = conn.execute(
                        """
                        SELECT path FROM skills
                        WHERE user_id = ? AND skill_name = ? AND version = ?
                        """,
                        (user_id, skill_name, old_active_version),
                    ).fetchone()
                    old_active_path = str((old_row["path"] if old_row else "") or "")
                    conn.execute(
                        """
                        UPDATE skills
                        SET path = '', archived_ts = ?, archived_reason = ?, superseded_by = NULL
                        WHERE user_id = ? AND skill_name = ? AND version = ?
                        """,
                        (int(time.time()), "user_archived", user_id, skill_name, old_active_version),
                    )

                skill_md_content = str(row["skill_md_content"] or "")
                rules_json_content = str(row["rules_json_content"] or "")
                if not skill_md_content and not rules_json_content:
                    return False

                new_dir = Path(base_dir) / user_id / f"{skill_name}-{version}"
                new_dir.mkdir(parents=True, exist_ok=True)
                (new_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
                (new_dir / "rules.json").write_text(rules_json_content, encoding="utf-8")
                restored_path = str(new_dir)

                conn.execute(
                    """
                    UPDATE skills
                    SET path = ?,
                        archived_ts = NULL,
                        archived_reason = NULL,
                        superseded_by = NULL
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (restored_path, user_id, skill_name, version),
                )
                conn.commit()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

        if old_active_path:
            old_dir = Path(old_active_path)
            if old_dir.exists() and old_dir.is_dir():
                for p in sorted(old_dir.rglob("*"), reverse=True):
                    if p.is_file():
                        p.unlink(missing_ok=True)
                    elif p.is_dir():
                        p.rmdir()
                old_dir.rmdir()

        if not restored_path:
            return False

        catalog_md = self.generate_catalog_snapshot(user_id)
        catalog_path = Path(base_dir) / user_id / "SKILL_CATALOG.md"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(catalog_md, encoding="utf-8")
        return True

    def get_active_skills(self, user_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM skills
                WHERE user_id = ? AND path != ''
                ORDER BY created_ts DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_archived_skills(self, user_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM skills
                WHERE user_id = ? AND path = ''
                ORDER BY archived_ts DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_skill_history(self, user_id: str, skill_name: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM skills
                WHERE user_id = ? AND skill_name = ?
                ORDER BY created_ts ASC
                """,
                (user_id, skill_name),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all_active_hashes(self, user_id: str) -> Dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT skill_name, content_hash FROM skills
                WHERE user_id = ? AND path != ''
                """,
                (user_id,),
            ).fetchall()
        return {str(r["skill_name"]): str(r["content_hash"] or "") for r in rows}

    @staticmethod
    def _format_ts(ts: Optional[int]) -> str:
        if not ts:
            return "-"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))

    def generate_catalog_snapshot(self, user_id: str) -> str:
        active = self.get_active_skills(user_id)
        archived = self.get_archived_skills(user_id)

        lines: List[str] = []
        lines.append(f"# Skill 目录 - {user_id}\n")
        lines.append(f"更新时间：{self._format_ts(int(time.time()))}\n\n")

        lines.append(f"## Active（{len(active)}条）\n\n")
        for row in active:
            lines.append(f"### {row.get('skill_name', '')}（{row.get('version', '')}）\n")
            lines.append(f"- 场景：{row.get('scene', '')}\n")
            lines.append(f"- 策略：{row.get('strategy', '')}\n")
            lines.append(f"- 规则：{row.get('rule_text', '')}\n")
            lines.append(f"- 置信度：{row.get('confidence', 0)}\n")
            lines.append(f"- 生效时间：{self._format_ts(row.get('created_ts'))}\n\n")

        lines.append(f"## Archived（{len(archived)}条）\n\n")
        for row in archived:
            lines.append(f"### {row.get('skill_name', '')}（{row.get('version', '')}）\n")
            lines.append(f"- 规则：{row.get('rule_text', '')}\n")
            lines.append(f"- 归档原因：{row.get('archived_reason', '')}\n")
            lines.append(f"- 被替代为：{row.get('superseded_by', '')}\n")
            lines.append(f"- 归档时间：{self._format_ts(row.get('archived_ts'))}\n\n")

        return "".join(lines)


_db = SkillDB()
