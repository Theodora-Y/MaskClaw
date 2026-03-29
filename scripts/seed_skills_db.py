#!/usr/bin/env python3
"""
将 generate_skills.py 生成的 Skill 文件批量写入 skill_registry.db。
不依赖 generate_skills.py 的内部函数，单独运行。

Usage: python3 scripts/seed_skills_db.py
"""

import json
import os
import sys
import time
import hashlib
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SKILL_REGISTRY_DB = PROJECT_ROOT / "skill_registry" / "skill_registry.db"

# 确保表已存在（通过 SkillDB）
sys.path.insert(0, str(PROJECT_ROOT))
try:
    from skill_registry.skill_db import SkillDB
    db = SkillDB(str(SKILL_REGISTRY_DB))
    print(f"[OK] SkillDB 初始化，表已就绪")
except Exception as e:
    print(f"[WARN] SkillDB 初始化失败: {e}")
    print("[INFO] 尝试直接建表...")

# ===== 建表 SQL（直接写入，无 trigger_count）=====
CREATE_SKILLS_TABLE = """
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

def ensure_table():
    conn = sqlite3.connect(str(SKILL_REGISTRY_DB))
    conn.execute(CREATE_SKILLS_TABLE)
    conn.commit()
    conn.close()

def add_or_replace_skill(conn: sqlite3.Connection, user_id: str, skill_dir: Path):
    """读取 skill_dir 下的 SKILL.md 和 rules.json，写入数据库。"""
    skill_md_path = skill_dir / "SKILL.md"
    rules_json_path = skill_dir / "rules.json"

    if not skill_md_path.exists() or not rules_json_path.exists():
        print(f"  [SKIP] 缺少文件: {skill_dir}")
        return False

    with open(skill_md_path, encoding="utf-8") as f:
        skill_md = f.read()
    with open(rules_json_path, encoding="utf-8") as f:
        rules_json = json.load(f)

    content_hash = hashlib.md5(skill_md.encode()).hexdigest()
    skill_name = skill_dir.parent.name  # skill_dir = .../wechat-send-message/v1.0.0
    version = "v1.0.0"
    path = str(skill_dir)

    try:
        conn.execute("""
            INSERT OR REPLACE INTO skills (
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
                path,
                float(rules_json.get("confidence", 0.85)),
                content_hash,
                str(rules_json.get("strategy", "")),
                str(rules_json.get("sensitive_field", "")),
                str(rules_json.get("scene", "")),
                str(rules_json.get("rule_text", "")),
                skill_md,
                json.dumps(rules_json, ensure_ascii=False),
                int(rules_json.get("created_ts", int(time.time()))),
            ),
        )
        return True
    except Exception as e:
        print(f"  [ERROR] 写入失败 {skill_name}: {e}")
        return False


def main():
    ensure_table()

    users = [
        ("demo_UserA", 1774000000, 1774000100),   # UserA: 新用户，ts集中在 2026-03-18
        ("demo_UserC", 1740500000, 1774600000),   # UserC: 老用户，ts分布在 2026-02 到 03
    ]

    conn = sqlite3.connect(str(SKILL_REGISTRY_DB))
    conn.execute("PRAGMA journal_mode=WAL")

    # 先清理 demo_UserA 和 demo_UserC 的旧记录（避免 skill_name="v1.0.0" 脏数据冲突）
    for uid in ["demo_UserA", "demo_UserC"]:
        deleted = conn.execute("DELETE FROM skills WHERE user_id = ?", (uid,)).rowcount
        if deleted:
            print(f"  [CLEAN] 清理 {uid} 旧记录 {deleted} 条")
    conn.commit()

    total = 0

    for user_id, ts_start, ts_end in users:
        base_dir = PROJECT_ROOT / "user_skills" / user_id
        if not base_dir.exists():
            print(f"[WARN] 目录不存在: {base_dir}")
            continue

        # 列出所有版本目录
        skill_dirs = []
        for sub_dir in sorted(base_dir.iterdir()):
            if sub_dir.is_dir():
                version_dir = sub_dir / "v1.0.0"
                if version_dir.exists():
                    skill_dirs.append(version_dir)

        print(f"\n>>> {user_id}: 找到 {len(skill_dirs)} 个 Skill")

        for skill_dir in skill_dirs:
            ok = add_or_replace_skill(conn, user_id, skill_dir)
            if ok:
                print(f"  [OK] {skill_dir.parent.name}")
                total += 1

        conn.commit()

    conn.close()

    # 验证
    conn2 = sqlite3.connect(str(SKILL_REGISTRY_DB))
    conn2.row_factory = sqlite3.Row
    for user_id, _, _ in users:
        count = conn2.execute(
            "SELECT COUNT(*) FROM skills WHERE user_id = ? AND archived_ts IS NULL",
            (user_id,)
        ).fetchone()[0]
        print(f"[DB] {user_id}: {count} 条 active skills")
    conn2.close()

    print(f"\n完成，共写入 {total} 条 Skill 到 skill_registry.db")


if __name__ == "__main__":
    main()
