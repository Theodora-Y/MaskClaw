"""SQLite-backed Skill registry with version history support.

Tables:
- skills: L2 隐私规则版本管理
- session_trace: 会话轨迹重建
- sop_draft: SOP 草稿（多轮迭代中）
- sop_version: 已发布的 SOP 版本
"""

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

    SOP_DRAFT_STAGES = ("diagnose", "draft", "validate", "ready")
    SOP_DRAFT_STAGE_ORDER = {"diagnose": 0, "draft": 1, "validate": 2, "ready": 3}

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
                # 原有 skills 表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS skills (
                      id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id            TEXT    NOT NULL,
                      skill_name         TEXT    NOT NULL,
                      version            TEXT    NOT NULL,
                      path               TEXT    NOT NULL,
                      confidence         REAL,
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
                # 会话轨迹表：用于 SOP 进化时重建完整操作序列
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS session_trace (
                      id               INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id          TEXT    NOT NULL,
                      session_id       TEXT    NOT NULL,
                      start_ts         INTEGER,
                      end_ts           INTEGER,
                      app_context      TEXT,
                      task_goal        TEXT,
                      raw_trace_json   TEXT,
                      has_correction   INTEGER DEFAULT 0,
                      correction_count INTEGER DEFAULT 0,
                      trace_hash       TEXT,
                      created_ts       INTEGER NOT NULL,
                      UNIQUE(user_id, session_id)
                    )
                    """
                )
                # SOP 草稿表：多轮迭代过程中的中间产物
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sop_draft (
                      id               INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id          TEXT    NOT NULL,
                      draft_name       TEXT    NOT NULL,
                      iteration        INTEGER DEFAULT 1,
                      stage            TEXT    DEFAULT 'init',
                      
                      -- 诊断结果
                      diagnose_result  TEXT,
                      app_context      TEXT,
                      task_goal        TEXT,
                      session_ids      TEXT,
                      
                      -- 当前 SOP 内容
                      current_content  TEXT,
                      
                      -- 爬山法相关
                      score            REAL    DEFAULT 0.0,
                      best_score       REAL    DEFAULT 0.0,
                      candidate_content TEXT,
                      test_results     TEXT,
                      checklist_scores TEXT,
                      
                      -- 历史记录
                      mutation_log     TEXT,
                      revert_count    INTEGER DEFAULT 0,
                      
                      -- 原始输出
                      diagnose_raw     TEXT,
                      mutate_raw       TEXT,
                      
                      -- 元数据
                      confidence       REAL    DEFAULT 0.0,
                      error_msg        TEXT,
                      created_ts       INTEGER NOT NULL,
                      updated_ts       INTEGER,
                      UNIQUE(user_id, draft_name, iteration)
                    )
                    """
                )
                # SOP 版本表：已发布的 SOP 技能
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sop_version (
                      id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id            TEXT    NOT NULL,
                      skill_name         TEXT    NOT NULL,
                      version             TEXT    NOT NULL,
                      path               TEXT    NOT NULL,
                      app_context        TEXT,
                      task_description   TEXT,
                      confidence         REAL,
                      source_sessions    TEXT,
                      skill_md_content   TEXT,
                      scripts_json       TEXT,
                      rules_json_content TEXT,
                      status             TEXT    DEFAULT 'active',
                      created_ts         INTEGER NOT NULL,
                      UNIQUE(user_id, skill_name, version)
                    )
                    """
                )
                # 通知表：用户待确认的规则变更通知
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notifications (
                      id            INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id       TEXT    NOT NULL,
                      notif_type    TEXT    NOT NULL,
                      title         TEXT    NOT NULL,
                      body          TEXT,
                      skill_name    TEXT,
                      skill_version TEXT,
                      event_id      TEXT,
                      status        TEXT    DEFAULT 'pending',
                      created_ts    INTEGER NOT NULL,
                      read_ts       INTEGER,
                      UNIQUE(user_id, event_id)
                    )
                    """
                )
                conn.commit()

                # 表迁移：检查并添加新列
                self._migrate_tables(conn)

        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def _migrate_tables(self, conn: sqlite3.Connection) -> None:
        """迁移表结构，添加新列（如果不存在）"""
        # sop_draft 表新增列
        new_columns_sop_draft = [
            ("app_context", "TEXT"),
            ("task_goal", "TEXT"),
            ("current_content", "TEXT"),
            ("candidate_content", "TEXT"),
            ("test_results", "TEXT"),
            ("checklist_scores", "TEXT"),
            ("mutation_log", "TEXT"),
            ("mutate_raw", "TEXT"),
            ("score", "REAL DEFAULT 0.0"),
            ("best_score", "REAL DEFAULT 0.0"),
            ("revert_count", "INTEGER DEFAULT 0"),
            ("last_sandbox_error", "TEXT"),
            ("is_best", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in new_columns_sop_draft:
            try:
                conn.execute(f"ALTER TABLE sop_draft ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # 列已存在

        # session_trace 表新增 processed 字段
        new_columns_session_trace = [
            ("processed", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_type in new_columns_session_trace:
            try:
                conn.execute(f"ALTER TABLE session_trace ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # 列已存在

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
                      confidence, content_hash,
                      strategy, sensitive_field, scene, rule_text,
                      skill_md_content, rules_json_content,
                      created_ts, archived_ts, archived_reason, superseded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                    """,
                    (
                        user_id,
                        skill_name,
                        version,
                        str(path),
                        float(rule_dict.get("confidence", 0.0)),
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

    def seed_default_skills_for_user(
        self,
        user_id: str,
        template_base: str | Path | None = None,
    ) -> int:
        """
        为新注册用户播种默认 Skill。
        从 _templates/basic/ 模板目录复制所有 skill 到 user_skills/{user_id}/，
        并写入 skill_registry.db。
        """
        import hashlib
        import shutil
        from pathlib import Path

        PROJECT_ROOT = Path(__file__).parent.parent
        TEMPLATE_BASE = Path(template_base) if template_base else (PROJECT_ROOT / "user_skills" / "_templates" / "basic")
        USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"

        if not TEMPLATE_BASE.exists():
            import logging
            logging.getLogger(__name__).warning(f"[seed_default_skills] template dir not found: {TEMPLATE_BASE}")
            return 0

        user_dir = USER_SKILLS_ROOT / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        ts = int(time.time())

        for skill_dir in sorted(TEMPLATE_BASE.iterdir()):
            if not skill_dir.is_dir():
                continue
            version_dir = skill_dir / "v1.0.0"
            if not version_dir.exists():
                continue

            dest_version = user_dir / skill_dir.name / "v1.0.0"
            if dest_version.exists():
                continue

            dest_version.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(version_dir, dest_version)

            skill_md_path = dest_version / "SKILL.md"
            rules_json_path = dest_version / "rules.json"
            if not skill_md_path.exists() or not rules_json_path.exists():
                continue

            with open(skill_md_path, encoding="utf-8") as f:
                skill_md = f.read()
            with open(rules_json_path, encoding="utf-8") as f:
                rules_json = json.load(f)

            content_hash = hashlib.md5(skill_md.encode()).hexdigest()
            try:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO skills (
                            user_id, skill_name, version, path,
                            confidence, content_hash,
                            strategy, sensitive_field, scene, rule_text,
                            skill_md_content, rules_json_content,
                            created_ts, archived_ts, archived_reason, superseded_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (
                            user_id,
                            skill_dir.name,
                            "v1.0.0",
                            str(dest_version),
                            float(rules_json.get("confidence", 0.85)),
                            content_hash,
                            str(rules_json.get("strategy", "")),
                            str(rules_json.get("sensitive_field", "")),
                            str(rules_json.get("scene", "")),
                            str(rules_json.get("rule_text", "")),
                            skill_md,
                            json.dumps(rules_json, ensure_ascii=False),
                            ts,
                        ),
                    )
                    conn.commit()
                count += 1
                import logging
                logging.getLogger(__name__).info(f"[seed_default_skills] registered {skill_dir.name} for {user_id}")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"[seed_default_skills] failed: {skill_dir.name}: {e}")

        return count

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

    def search_skills(
        self,
        user_id: str,
        task_goal: str = "",
        app_context: str = "",
        action_keywords: str = "",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """根据任务上下文检索匹配的 skills

        同时查询 skills 表和 sop_version 表。

        Args:
            user_id: 用户ID
            task_goal: 任务目标关键词（模糊匹配 rule_text 和 strategy）
            app_context: 应用上下文（精确匹配 scene 字段）
            action_keywords: 动作关键词（截图、发送等，模糊匹配 rule_text 和 strategy）
            limit: 返回数量限制

        Returns:
            匹配的 skills 列表，按置信度降序
        """
        results = []

        # 构建 WHERE 条件
        def build_conditions(table_fields):
            conditions = []
            params = []

            if 'path' in table_fields:
                conditions.append("path != ''")
            if 'status' in table_fields:
                conditions.append("status = 'active'")

            if app_context:
                # 优先匹配 scene/app_context 字段
                if 'scene' in table_fields:
                    conditions.append("scene LIKE ?")
                    params.append(f"%{app_context}%")
                elif 'app_context' in table_fields:
                    conditions.append("app_context LIKE ?")
                    params.append(f"%{app_context}%")

            if task_goal:
                if 'rule_text' in table_fields:
                    conditions.append("(rule_text LIKE ? OR strategy LIKE ?)")
                    params.extend([f"%{task_goal}%", f"%{task_goal}%"])
                elif 'task_description' in table_fields:
                    conditions.append("task_description LIKE ?")
                    params.append(f"%{task_goal}%")

            if action_keywords:
                if 'rule_text' in table_fields:
                    conditions.append("(rule_text LIKE ? OR strategy LIKE ?)")
                    params.extend([f"%{action_keywords}%", f"%{action_keywords}%"])
                elif 'task_description' in table_fields:
                    conditions.append("task_description LIKE ?")
                    params.append(f"%{action_keywords}%")

            return conditions, params

        # 1. 查询 skills 表
        with self._connect() as conn:
            skills_fields = [col[1] for col in conn.execute("PRAGMA table_info(skills)").fetchall()]
            conditions, params = build_conditions(skills_fields)

            if conditions:
                sql = f"""
                    SELECT *, 'skills' as source_table FROM skills
                    WHERE user_id = ? AND {' AND '.join(conditions)}
                    ORDER BY confidence DESC, trigger_count DESC, created_ts DESC
                    LIMIT ?
                """
                params = [user_id] + params + [limit]
                rows = conn.execute(sql, params).fetchall()
                results.extend([self._row_to_dict(r) for r in rows])

        # 2. 查询 sop_version 表
        with self._connect() as conn:
            version_fields = [col[1] for col in conn.execute("PRAGMA table_info(sop_version)").fetchall()]
            conditions, params = build_conditions(version_fields)

            if conditions:
                sql = f"""
                    SELECT *, 'sop_version' as source_table FROM sop_version
                    WHERE user_id = ? AND {' AND '.join(conditions)}
                    ORDER BY confidence DESC, created_ts DESC
                    LIMIT ?
                """
                params = [user_id] + params + [limit]
                rows = conn.execute(sql, params).fetchall()
                results.extend([self._row_to_dict(r) for r in rows])

        # 3. 去重并按置信度排序
        seen = set()
        unique_results = []
        for r in results:
            key = (r.get('skill_name'), r.get('version'))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return unique_results[:limit]

    def get_skill_detail(
        self,
        user_id: str,
        skill_name: str,
        version: str,
    ) -> Optional[Dict[str, Any]]:
        """获取完整 skill 详情

        优先从 skills 表查询，如果没找到则查询 sop_version 表。

        Args:
            user_id: 用户ID
            skill_name: 技能名称
            version: 版本号

        Returns:
            skill 详情（包含 SKILL.md 和 rules.json 内容），未找到返回 None
        """
        with self._connect() as conn:
            # 1. 先查询 skills 表
            row = conn.execute(
                """
                SELECT * FROM skills
                WHERE user_id = ? AND skill_name = ? AND version = ?
                """,
                (user_id, skill_name, version),
            ).fetchone()

        result = None
        if row:
            result = self._row_to_dict(row)
        else:
            # 2. 如果 skills 表没有，查询 sop_version 表
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM sop_version
                    WHERE user_id = ? AND skill_name = ? AND version = ?
                    """,
                    (user_id, skill_name, version),
                ).fetchone()
            if row:
                result = self._row_to_dict(row)

        if not result:
            return None

        # 如果有 path，尝试读取实际的 SKILL.md 和 rules.json
        path = result.get("path")
        if path:
            skill_dir = Path(path)
            skill_md = skill_dir / "SKILL.md"
            rules_json = skill_dir / "rules.json"

            if skill_md.exists():
                result["skill_md_content"] = skill_md.read_text(encoding="utf-8")
            if rules_json.exists():
                try:
                    result["rules_json_content"] = json.loads(rules_json.read_text(encoding="utf-8"))
                except Exception:
                    result["rules_json_content"] = None

        return result

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

    # ============== SOP 进化相关方法 ==============

    def add_session_trace(
        self,
        user_id: str,
        session_id: str,
        trace_data: Dict[str, Any],
    ) -> bool:
        """添加会话轨迹记录，返回是否新增成功（去重）"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                trace_json = json.dumps(trace_data, ensure_ascii=False)
                trace_hash = hashlib.md5(trace_json.encode()).hexdigest()

                try:
                    now_ts = int(time.time())
                    conn.execute(
                        """
                        INSERT INTO session_trace (
                          user_id, session_id, start_ts, end_ts, app_context,
                          task_goal, raw_trace_json, has_correction,
                          correction_count, trace_hash, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            session_id,
                            trace_data.get("start_ts"),
                            trace_data.get("end_ts"),
                            trace_data.get("app_context", ""),
                            trace_data.get("task_goal", ""),
                            trace_json,
                            int(trace_data.get("has_correction", 0)),
                            int(trace_data.get("correction_count", 0)),
                            trace_hash,
                            now_ts,
                        ),
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_pending_traces(
        self,
        user_id: str,
        min_corrections: int = 1,
    ) -> List[Dict[str, Any]]:
        """获取有待纠错的会话轨迹"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_trace
                WHERE user_id = ? AND has_correction >= ? AND correction_count >= ?
                ORDER BY created_ts DESC
                """,
                (user_id, min_corrections, min_corrections),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_session_trace(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单条会话轨迹"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM session_trace WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def upsert_sop_draft(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
        stage: str,
        diagnose_result: Optional[str] = None,
        draft_content: Optional[str] = None,
        validation_result: Optional[str] = None,
        diagnose_raw: Optional[str] = None,
        draft_raw: Optional[str] = None,
        validate_raw: Optional[str] = None,
        confidence: float = 0.0,
        session_ids: Optional[List[str]] = None,
        error_msg: Optional[str] = None,
    ) -> bool:
        """插入或更新 SOP 草稿"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                session_ids_json = json.dumps(session_ids or [], ensure_ascii=False)

                conn.execute(
                    """
                    INSERT INTO sop_draft (
                      user_id, draft_name, iteration, stage,
                      diagnose_result, draft_content, validation_result,
                      diagnose_raw, draft_raw, validate_raw,
                      confidence, session_ids, error_msg,
                      created_ts, updated_ts
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, draft_name, iteration) DO UPDATE SET
                      stage = excluded.stage,
                      diagnose_result = COALESCE(excluded.diagnose_result, diagnose_result),
                      draft_content = COALESCE(excluded.draft_content, draft_content),
                      validation_result = COALESCE(excluded.validation_result, validation_result),
                      diagnose_raw = COALESCE(excluded.diagnose_raw, diagnose_raw),
                      draft_raw = COALESCE(excluded.draft_raw, draft_raw),
                      validate_raw = COALESCE(excluded.validate_raw, validate_raw),
                      confidence = excluded.confidence,
                      session_ids = COALESCE(excluded.session_ids, session_ids),
                      error_msg = excluded.error_msg,
                      updated_ts = excluded.updated_ts
                    """,
                    (
                        user_id,
                        draft_name,
                        iteration,
                        stage,
                        diagnose_result,
                        draft_content,
                        validation_result,
                        diagnose_raw,
                        draft_raw,
                        validate_raw,
                        float(confidence),
                        session_ids_json,
                        error_msg,
                        now_ts,
                        now_ts,
                    ),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_sop_draft(
        self,
        user_id: str,
        draft_name: str,
        iteration: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取 SOP 草稿"""
        with self._connect() as conn:
            if iteration is not None:
                row = conn.execute(
                    "SELECT * FROM sop_draft WHERE user_id = ? AND draft_name = ? AND iteration = ?",
                    (user_id, draft_name, iteration),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sop_draft WHERE user_id = ? AND draft_name = ? ORDER BY iteration DESC LIMIT 1",
                    (user_id, draft_name),
                ).fetchone()
        if row:
            result = self._row_to_dict(row)
            if result.get("session_ids"):
                try:
                    result["session_ids"] = json.loads(result["session_ids"])
                except json.JSONDecodeError:
                    result["session_ids"] = []
            return result
        return None

    def get_all_sop_drafts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有 SOP 草稿"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sop_draft WHERE user_id = ? ORDER BY iteration DESC",
                (user_id,),
            ).fetchall()
        results = []
        for row in rows:
            result = self._row_to_dict(row)
            if result.get("session_ids"):
                try:
                    result["session_ids"] = json.loads(result["session_ids"])
                except json.JSONDecodeError:
                    result["session_ids"] = []
            results.append(result)
        return results

    def get_ready_drafts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取处于 ready 阶段、待沙盒验证的草稿"""
        return [
            d for d in self.get_all_sop_drafts(user_id)
            if d.get("stage") == "ready"
        ]

    def publish_sop_version(
        self,
        user_id: str,
        skill_name: str,
        version: str,
        path: str,
        app_context: str,
        task_description: str,
        confidence: float,
        source_sessions: List[str],
        skill_md_content: str,
        scripts_json: Optional[str] = None,
        rules_json_content: Optional[str] = None,
    ) -> bool:
        """发布 SOP 版本"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                source_sessions_json = json.dumps(source_sessions, ensure_ascii=False)

                try:
                    conn.execute(
                        """
                        INSERT INTO sop_version (
                          user_id, skill_name, version, path,
                          app_context, task_description, confidence,
                          source_sessions, skill_md_content,
                          scripts_json, rules_json_content,
                          status, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                        """,
                        (
                            user_id,
                            skill_name,
                            version,
                            path,
                            app_context,
                            task_description,
                            float(confidence),
                            source_sessions_json,
                            skill_md_content,
                            scripts_json,
                            rules_json_content,
                            now_ts,
                        ),
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_active_sop_versions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户所有活跃的 SOP 版本"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sop_version WHERE user_id = ? AND status = 'active' ORDER BY created_ts DESC",
                (user_id,),
            ).fetchall()
        results = []
        for row in rows:
            result = self._row_to_dict(row)
            if result.get("source_sessions"):
                try:
                    result["source_sessions"] = json.loads(result["source_sessions"])
                except json.JSONDecodeError:
                    result["source_sessions"] = []
            results.append(result)
        return results

    def get_sop_version(
        self,
        user_id: str,
        skill_name: str,
        version: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """获取指定 SOP 版本"""
        with self._connect() as conn:
            if version:
                row = conn.execute(
                    "SELECT * FROM sop_version WHERE user_id = ? AND skill_name = ? AND version = ?",
                    (user_id, skill_name, version),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sop_version WHERE user_id = ? AND skill_name = ? AND status = 'active' ORDER BY created_ts DESC LIMIT 1",
                    (user_id, skill_name),
                ).fetchone()
        if row:
            result = self._row_to_dict(row)
            if result.get("source_sessions"):
                try:
                    result["source_sessions"] = json.loads(result["source_sessions"])
                except json.JSONDecodeError:
                    result["source_sessions"] = []
            return result
        return None

    def archive_sop_version(
        self,
        user_id: str,
        skill_name: str,
        version: str,
    ) -> bool:
        """归档 SOP 版本"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE sop_version SET status = 'archived' WHERE user_id = ? AND skill_name = ? AND version = ?",
                    (user_id, skill_name, version),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_ready_drafts_for_publish(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """获取所有待发布的草稿（沙盒已通过）"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sop_draft
                WHERE user_id = ? AND stage = 'ready'
                ORDER BY confidence DESC, updated_ts DESC
                """,
                (user_id,),
            ).fetchall()
        results = []
        for row in rows:
            result = self._row_to_dict(row)
            if result.get("session_ids"):
                try:
                    result["session_ids"] = json.loads(result["session_ids"])
                except json.JSONDecodeError:
                    result["session_ids"] = []
            results.append(result)
        return results

    def mark_draft_published(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
    ) -> bool:
        """标记草稿已发布"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE sop_draft SET stage = 'published' WHERE user_id = ? AND draft_name = ? AND iteration = ?",
                    (user_id, draft_name, iteration),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    # ============== 爬山法 SOP 进化相关方法 ==============

    def init_sop_draft(
        self,
        user_id: str,
        draft_name: str,
        app_context: str,
        task_goal: str,
        session_ids: List[str],
        initial_content: Optional[str] = None,
    ) -> bool:
        """初始化一个新的 SOP 草稿（爬山法）"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                session_ids_json = json.dumps(session_ids or [], ensure_ascii=False)

                # 查找下一个 iteration
                row = conn.execute(
                    "SELECT MAX(iteration) as max_iter FROM sop_draft WHERE user_id = ? AND draft_name = ?",
                    (user_id, draft_name),
                ).fetchone()
                next_iter = (row["max_iter"] or 0) + 1

                conn.execute(
                    """
                    INSERT INTO sop_draft (
                      user_id, draft_name, iteration, stage,
                      app_context, task_goal, session_ids,
                      current_content, candidate_content,
                      score, best_score, mutation_log, revert_count,
                      created_ts, updated_ts
                    ) VALUES (?, ?, ?, 'init', ?, ?, ?, ?, NULL, 0.0, 0.0, '[]', 0, ?, ?)
                    """,
                    (
                        user_id,
                        draft_name,
                        next_iter,
                        app_context,
                        task_goal,
                        session_ids_json,
                        initial_content or "",
                        now_ts,
                        now_ts,
                    ),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_sop_draft_for_evolution(
        self,
        user_id: str,
        draft_name: str,
    ) -> Optional[Dict[str, Any]]:
        """获取最新草稿用于进化"""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sop_draft 
                WHERE user_id = ? AND draft_name = ? 
                ORDER BY iteration DESC LIMIT 1
                """,
                (user_id, draft_name),
            ).fetchone()
        
        if row:
            return self._parse_sop_draft_row(row)
        return None

    def _parse_sop_draft_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        """解析 SOP 草稿行"""
        result = self._row_to_dict(row)
        
        # 解析 JSON 字段
        for field in ["session_ids", "test_results", "checklist_scores", "mutation_log"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = [] if field in ["session_ids", "test_results", "mutation_log"] else {}
        
        return result

    def update_draft_mutation(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
        candidate_content: str,
        score: float,
        checklist_scores: Dict[str, Any],
        test_results: List[Dict[str, Any]],
        mutate_raw: Optional[str] = None,
    ) -> bool:
        """更新变异结果"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                test_results_json = json.dumps(test_results, ensure_ascii=False)
                checklist_scores_json = json.dumps(checklist_scores, ensure_ascii=False)

                # 获取当前 best_score
                row = conn.execute(
                    "SELECT best_score, current_content, mutation_log FROM sop_draft WHERE user_id = ? AND draft_name = ? AND iteration = ?",
                    (user_id, draft_name, iteration),
                ).fetchone()

                if not row:
                    return False

                current_best = float(row["best_score"] or 0.0)
                current_content = str(row["current_content"] or "")
                mutation_log = json.loads(row["mutation_log"] or "[]")

                # 爬山法决策
                if score > current_best:
                    # 比当前更好，保留变异
                    new_best = score
                    new_content = candidate_content
                    decision = "accept"
                else:
                    # 比当前差，撤销变异
                    new_best = current_best
                    new_content = current_content
                    decision = "reject"

                # 记录变异日志
                mutation_log.append({
                    "ts": now_ts,
                    "score": score,
                    "decision": decision,
                    "checklist": checklist_scores,
                })

                mutation_log_json = json.dumps(mutation_log, ensure_ascii=False)

                conn.execute(
                    """
                    UPDATE sop_draft SET
                      candidate_content = ?,
                      score = ?,
                      best_score = MAX(best_score, ?),
                      current_content = ?,
                      test_results = ?,
                      checklist_scores = ?,
                      mutation_log = ?,
                      mutate_raw = COALESCE(?, mutate_raw),
                      updated_ts = ?
                    WHERE user_id = ? AND draft_name = ? AND iteration = ?
                    """,
                    (
                        candidate_content,
                        score,
                        score,
                        new_content,
                        test_results_json,
                        checklist_scores_json,
                        mutation_log_json,
                        mutate_raw,
                        now_ts,
                        user_id,
                        draft_name,
                        iteration,
                    ),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def update_draft_stage(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
        stage: str,
        error_msg: Optional[str] = None,
    ) -> bool:
        """更新草稿阶段"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                conn.execute(
                    """
                    UPDATE sop_draft SET 
                      stage = ?,
                      error_msg = COALESCE(?, error_msg),
                      updated_ts = ?
                    WHERE user_id = ? AND draft_name = ? AND iteration = ?
                    """,
                    (stage, error_msg, now_ts, user_id, draft_name, iteration),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_consecutive_high_scores(
        self,
        user_id: str,
        draft_name: str,
        threshold: float = 0.9,
        consecutive_count: int = 3,
    ) -> Dict[str, Any]:
        """检查是否连续多轮达到高分数阈值"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT iteration, score, best_score 
                FROM sop_draft 
                WHERE user_id = ? AND draft_name = ?
                ORDER BY iteration DESC
                LIMIT ?
                """,
                (user_id, draft_name, consecutive_count),
            ).fetchall()

        if len(rows) < consecutive_count:
            return {"consecutive": False, "count": len(rows), "threshold": threshold}

        consecutive_hits = 0
        for row in rows:
            if float(row["score"]) >= threshold or float(row["best_score"]) >= threshold:
                consecutive_hits += 1
            else:
                break

        return {
            "consecutive": consecutive_hits >= consecutive_count,
            "count": consecutive_hits,
            "threshold": threshold,
            "required": consecutive_count,
        }

    def save_session_trace_full(
        self,
        user_id: str,
        session_id: str,
        app_context: str,
        task_goal: str,
        behaviors: List[Dict[str, Any]],
        corrections: List[Dict[str, Any]],
        chain_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """保存完整会话轨迹。

        Args:
            chain_metadata: v2.0 新增，包含 rule_type, start_ts, end_ts 等链级元数据
        """
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                # 支持 timestamp 和 ts 两种字段
                all_items = behaviors + corrections
                timestamps = []
                for item in all_items:
                    ts = item.get("timestamp") or item.get("ts") or 0
                    if ts:
                        timestamps.append(ts)

                # v2.0: 优先使用 chain_metadata 中的时间
                if chain_metadata:
                    start_ts = chain_metadata.get("start_ts") or min(timestamps) if timestamps else 0
                    end_ts = chain_metadata.get("end_ts") or max(timestamps) if timestamps else 0
                    rule_type = chain_metadata.get("rule_type", "N")
                    action_count = chain_metadata.get("action_count", len(all_items))
                    has_correction = chain_metadata.get("has_correction", len(corrections) > 0)
                    final_resolution = chain_metadata.get("final_resolution", "unknown")
                else:
                    start_ts = min(timestamps) if timestamps else 0
                    end_ts = max(timestamps) if timestamps else 0
                    rule_type = "N"
                    action_count = len(all_items)
                    has_correction = len(corrections) > 0
                    final_resolution = "unknown"

                trace_data = {
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "app_context": app_context,
                    "task_goal": task_goal,
                    "behaviors": behaviors,
                    "corrections": corrections,
                    "correction_count": len(corrections),
                    "has_correction": has_correction,
                    "rule_type": rule_type,
                    "action_count": action_count,
                    "final_resolution": final_resolution,
                }

                trace_json = json.dumps(trace_data, ensure_ascii=False)
                trace_hash = hashlib.md5(trace_json.encode()).hexdigest()

                now_ts = int(time.time())
                try:
                    conn.execute(
                        """
                        INSERT INTO session_trace (
                          user_id, session_id, start_ts, end_ts, app_context,
                          task_goal, raw_trace_json, has_correction,
                          correction_count, trace_hash, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, session_id) DO UPDATE SET
                          raw_trace_json = excluded.raw_trace_json,
                          correction_count = excluded.correction_count,
                          has_correction = excluded.has_correction
                        """,
                        (
                            user_id,
                            session_id,
                            trace_data["start_ts"],
                            trace_data["end_ts"],
                            app_context,
                            task_goal,
                            trace_json,
                            int(trace_data["has_correction"]),
                            trace_data["correction_count"],
                            trace_hash,
                            now_ts,
                        ),
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_test_scenarios_from_traces(
        self,
        user_id: str,
        app_context: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """从会话轨迹中提取测试场景"""
        with self._connect() as conn:
            if app_context:
                rows = conn.execute(
                    """
                    SELECT * FROM session_trace
                    WHERE user_id = ? AND app_context = ? AND has_correction = 1
                    ORDER BY created_ts DESC
                    LIMIT ?
                    """,
                    (user_id, app_context, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM session_trace
                    WHERE user_id = ? AND has_correction = 1
                    ORDER BY created_ts DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()

        scenarios = []
        for row in rows:
            trace = json.loads(row["raw_trace_json"] or "{}")
            # 提取场景：任务目标 + 关键行为序列
            scenarios.append({
                "session_id": row["session_id"],
                "app_context": row["app_context"],
                "task_goal": row["task_goal"],
                "behaviors": trace.get("behaviors", []),
                "corrections": trace.get("corrections", []),
                "correct_flow": self._extract_correct_flow(trace),
            })

        return scenarios

    def _extract_correct_flow(self, trace: Dict[str, Any]) -> List[str]:
        """从轨迹中提取正确流程"""
        behaviors = trace.get("behaviors", [])
        corrections = trace.get("corrections", [])

        if not corrections:
            return [b.get("action", "") for b in behaviors]

        # 过滤掉被纠正的行为
        corrected_actions = {c.get("action") for c in corrections if c.get("action")}
        return [
            b.get("action", "")
            for b in behaviors
            if b.get("action") not in corrected_actions
        ]

    # ============== 进化流水线支持方法 ==============

    def mark_traces_processed(self, user_id: str, session_ids: List[str]) -> int:
        """标记会话轨迹为已处理（processed = 1）

        Args:
            user_id: 用户ID
            session_ids: 要标记的 session_id 列表

        Returns:
            实际更新的记录数
        """
        if not session_ids:
            return 0

        placeholders = ",".join(["?"] * len(session_ids))
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    f"""
                    UPDATE session_trace
                    SET processed = 1
                    WHERE user_id = ? AND session_id IN ({placeholders}) AND processed = 0
                    """,
                    [user_id] + session_ids,
                )
                conn.commit()
                return cursor.rowcount
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def update_sandbox_error(
        self,
        user_id: str,
        draft_name: str,
        error_msg: str,
    ) -> bool:
        """更新草稿的最后沙盒错误

        Args:
            user_id: 用户ID
            draft_name: 草稿名
            error_msg: 沙盒错误信息

        Returns:
            是否更新成功
        """
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                conn.execute(
                    """
                    UPDATE sop_draft SET
                      last_sandbox_error = ?,
                      updated_ts = ?
                    WHERE user_id = ? AND draft_name = ? AND is_best = 1
                    """,
                    (error_msg, now_ts, user_id, draft_name),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def set_best_draft(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
    ) -> bool:
        """将指定草稿设为最优版本

        Args:
            user_id: 用户ID
            draft_name: 草稿名
            iteration: 迭代轮次

        Returns:
            是否更新成功
        """
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())

                # 取消所有 is_best 标记
                conn.execute(
                    """
                    UPDATE sop_draft SET is_best = 0
                    WHERE user_id = ? AND draft_name = ?
                    """,
                    (user_id, draft_name),
                )

                # 设置新的 is_best
                conn.execute(
                    """
                    UPDATE sop_draft SET
                      is_best = 1,
                      updated_ts = ?
                    WHERE user_id = ? AND draft_name = ? AND iteration = ?
                    """,
                    (now_ts, user_id, draft_name, iteration),
                )

                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_checkpoint(self, user_id: str, draft_name: str) -> Optional[Dict[str, Any]]:
        """获取断点续传信息

        自动查找 is_best=1 且 stage='evolving' 的草稿。

        Args:
            user_id: 用户ID
            draft_name: 草稿名

        Returns:
            断点信息 dict，若无断点则返回 None
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM sop_draft
                WHERE user_id = ? AND draft_name = ? AND is_best = 1
                ORDER BY iteration DESC
                LIMIT 1
                """,
                (user_id, draft_name),
            ).fetchone()

            if row:
                return self._parse_sop_draft_row(row)
            return None

    def mark_evolution_failed(
        self,
        user_id: str,
        draft_name: str,
        reason: str,
    ) -> bool:
        """标记进化失败，需要人工介入

        Args:
            user_id: 用户ID
            draft_name: 草稿名
            reason: 失败原因

        Returns:
            是否更新成功
        """
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                now_ts = int(time.time())
                conn.execute(
                    """
                    UPDATE sop_draft SET
                      stage = 'failed',
                      error_msg = ?,
                      updated_ts = ?
                    WHERE user_id = ? AND draft_name = ? AND is_best = 1
                    """,
                    (f"MAX_ITERATIONS_EXCEEDED: {reason}", now_ts, user_id, draft_name),
                )
                conn.commit()
                return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_unprocessed_traces(
        self,
        user_id: str,
        min_corrections: int = 1,
    ) -> List[Dict[str, Any]]:
        """获取未处理的会话轨迹（processed = 0）

        Args:
            user_id: 用户ID
            min_corrections: 最少纠错数量

        Returns:
            未处理的轨迹列表
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM session_trace
                WHERE user_id = ? AND processed = 0 AND has_correction >= ?
                ORDER BY created_ts DESC
                """,
                (user_id, min_corrections),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all_user_ids(self) -> List[str]:
        """获取所有有 session_trace 记录的用户 ID

        Returns:
            用户 ID 列表
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT user_id FROM session_trace
                ORDER BY user_id
                """
            ).fetchall()
        return [str(row[0]) for row in rows]

    # ===== Notifications =====

    def get_notifications(
        self,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Dict[str, Any]], int]:
        """获取用户通知列表。

        Args:
            user_id: 用户ID
            status: 可选，筛选 pending / confirmed / dismissed
            page: 页码（从1开始）
            page_size: 每页条数

        Returns:
            (通知列表, 总数)
        """
        with self._connect() as conn:
            where = ["user_id = ?"]
            params: list = [user_id]
            if status:
                where.append("status = ?")
                params.append(status)

            where_clause = " AND ".join(where)

            total = conn.execute(
                f"SELECT COUNT(*) FROM notifications WHERE {where_clause}",
                params,
            ).fetchone()[0]

            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT * FROM notifications
                WHERE {where_clause}
                ORDER BY created_ts DESC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()

        return [self._row_to_dict(r) for r in rows], total

    def add_notification(
        self,
        user_id: str,
        notif_type: str,
        title: str,
        body: str | None = None,
        skill_name: str | None = None,
        skill_version: str | None = None,
        event_id: str | None = None,
        status: str = "pending",
    ) -> bool:
        """新增一条通知（忽略重复的 event_id）。"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                try:
                    conn.execute(
                        """
                        INSERT INTO notifications (
                          user_id, notif_type, title, body,
                          skill_name, skill_version, event_id,
                          status, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id, notif_type, title, body,
                            skill_name, skill_version, event_id,
                            status,
                            int(time.time()),
                        ),
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False  # 重复的 event_id
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def mark_notification_read(self, user_id: str, notif_id: int) -> bool:
        """标记单条通知为已读。"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE notifications
                    SET read_ts = ?, status = 'confirmed'
                    WHERE id = ? AND user_id = ? AND read_ts IS NULL
                    """,
                    (int(time.time()), notif_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def mark_all_notifications_read(self, user_id: str) -> int:
        """全部标记为已读，返回影响行数。"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE notifications
                    SET read_ts = ?, status = 'confirmed'
                    WHERE user_id = ? AND read_ts IS NULL
                    """,
                    (int(time.time()), user_id),
                )
                conn.commit()
                return cursor.rowcount
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def get_unread_count(self, user_id: str) -> int:
        """获取未读通知数量。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_ts IS NULL",
                (user_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def dismiss_notification(self, user_id: str, notif_id: int) -> bool:
        """将通知标记为 dismissed（拒绝/忽略）。"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE notifications
                    SET read_ts = ?, status = 'dismissed'
                    WHERE id = ? AND user_id = ?
                    """,
                    (int(time.time()), notif_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def seed_notifications(self, records: list[dict]) -> int:
        """批量写入通知记录（用于预制数据）。"""
        lock_file = self._with_lock()
        try:
            with self._connect() as conn:
                inserted = 0
                for r in records:
                    try:
                        conn.execute(
                            """
                            INSERT INTO notifications (
                              user_id, notif_type, title, body,
                              skill_name, skill_version, event_id,
                              status, created_ts
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                r["user_id"], r["notif_type"], r["title"],
                                r.get("body"), r.get("skill_name"),
                                r.get("skill_version"), r.get("event_id"),
                                r.get("status", "pending"),
                                r.get("created_ts", int(time.time())),
                            ),
                        )
                        inserted += 1
                    except sqlite3.IntegrityError:
                        pass  # 跳过重复
                conn.commit()
                return inserted
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()


_db = SkillDB()
