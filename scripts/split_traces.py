#!/usr/bin/env python3
"""统一日志格式工具 - 将 session_trace.jsonl 拆分为 correction_log.jsonl 和 behavior_log.jsonl

分类规则：
- has_correction=True → correction_log.jsonl (用户打断/纠错)
- has_correction=False → behavior_log.jsonl (流畅完成)

同时生成/更新 session_trace.jsonl 作为统一格式。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def trace_to_correction_entry(chain: Dict[str, Any]) -> Dict[str, Any]:
    """将链转换为 correction_log 条目格式。"""
    actions = chain.get("actions", [])
    # 取第一个有 correction 的动作作为代表
    correction_action = None
    for action in actions:
        if action.get("is_correction"):
            correction_action = action
            break
    if not correction_action:
        correction_action = actions[0] if actions else {}

    return {
        "event_id": chain.get("chain_id", ""),
        "user_id": chain.get("user_id", ""),
        "app_context": chain.get("app_context", "unknown"),
        "action": correction_action.get("action", "unknown"),
        "field": correction_action.get("field"),
        "resolution": correction_action.get("resolution", "blocked"),
        "correction_type": correction_action.get("correction_type", "user_denied"),
        "correction_value": correction_action.get("correction_value"),
        "_pii_type": correction_action.get("pii_type"),
        "_relationship_tag": correction_action.get("relationship_tag"),
        "_agent_intent": correction_action.get("agent_intent"),
        "_scenario_tag": chain.get("scenario_tag", ""),
        "_rule_type": chain.get("rule_type", "N"),
        "_quality_score": correction_action.get("quality_score"),
        "_quality_flag": correction_action.get("quality_flag"),
        "ts": chain.get("start_ts", 0),
        # 保留完整链信息
        "_chain_id": chain.get("chain_id", ""),
        "_action_count": chain.get("action_count", 0),
        "_correction_count": chain.get("correction_count", 0),
        "_final_resolution": chain.get("final_resolution", "unknown"),
    }


def trace_to_behavior_entry(chain: Dict[str, Any]) -> Dict[str, Any]:
    """将链转换为 behavior_log 条目格式。"""
    actions = chain.get("actions", [])
    return {
        "event_id": chain.get("chain_id", ""),
        "user_id": chain.get("user_id", ""),
        "app_context": chain.get("app_context", "unknown"),
        "action": actions[0].get("action", "unknown") if actions else "unknown",
        "field": actions[0].get("field") if actions else None,
        "resolution": chain.get("final_resolution", "allow"),
        "value_preview": None,
        "_pii_type": actions[0].get("pii_type") if actions else None,
        "_scenario_tag": chain.get("scenario_tag", ""),
        "_rule_type": chain.get("rule_type", "N"),
        "ts": chain.get("start_ts", 0),
        # 保留完整链信息
        "_chain_id": chain.get("chain_id", ""),
        "_action_count": chain.get("action_count", 0),
        "_end_ts": chain.get("end_ts", 0),
    }


def process_user(user_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """处理单个用户的日志目录。"""
    user_id = user_dir.name
    trace_path = user_dir / "session_trace.jsonl"

    # 读取现有的 trace
    traces = read_jsonl(trace_path)

    # 读取现有的 correction_log 和 behavior_log（用于追加或合并）
    existing_corrections = read_jsonl(user_dir / "correction_log.jsonl")
    existing_behaviors = read_jsonl(user_dir / "behavior_log.jsonl")

    corrections = []
    behaviors = []

    for chain in traces:
        if chain.get("has_correction"):
            corrections.append(trace_to_correction_entry(chain))
        else:
            behaviors.append(trace_to_behavior_entry(chain))

    # 写入文件
    if not dry_run:
        if corrections:
            write_jsonl(user_dir / "correction_log.jsonl", corrections)
        else:
            # 清空文件
            (user_dir / "correction_log.jsonl").write_text("", encoding="utf-8")

        if behaviors:
            write_jsonl(user_dir / "behavior_log.jsonl", behaviors)
        else:
            (user_dir / "behavior_log.jsonl").write_text("", encoding="utf-8")

    return {
        "user_id": user_id,
        "corrections": len(corrections),
        "behaviors": len(behaviors),
        "total_chains": len(traces),
    }


def main():
    parser = argparse.ArgumentParser(description="统一日志格式工具")
    parser.add_argument("--user", type=str, default=None, help="指定用户ID")
    parser.add_argument("--logs-root", type=str, default="memory/logs", help="日志根目录")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟")
    parser.add_argument("--list-users", action="store_true", help="列出所有用户")

    args = parser.parse_args()
    logs_root = Path(args.logs_root)

    # 列出用户
    if args.list_users:
        users = sorted([d.name for d in logs_root.iterdir() if d.is_dir()])
        print(f"用户列表 ({len(users)}):")
        for u in users:
            print(f"  - {u}")
        return

    # 确定用户
    if args.user:
        user_dirs = [logs_root / args.user]
        if not user_dirs[0].exists():
            print(f"用户目录不存在: {user_dirs[0]}")
            sys.exit(1)
    else:
        user_dirs = sorted([d for d in logs_root.iterdir() if d.is_dir()])

    print("=" * 60)
    print("统一日志格式工具")
    print("=" * 60)
    print(f"日志目录: {logs_root}")
    print(f"用户数量: {len(user_dirs)}")
    print(f"模拟运行: {args.dry_run}")
    print("=" * 60)

    for user_dir in user_dirs:
        trace_path = user_dir / "session_trace.jsonl"
        if not trace_path.exists():
            print(f"\n>>> 跳过 {user_dir.name}: 无 session_trace.jsonl")
            continue

        print(f"\n>>> 处理用户: {user_dir.name}")
        try:
            result = process_user(user_dir, dry_run=args.dry_run)
            if args.dry_run:
                print(f"  [DRY-RUN] 纠错链: {result['corrections']}, 正常链: {result['behaviors']}")
            else:
                print(f"  纠错链: {result['corrections']} → correction_log.jsonl")
                print(f"  正常链: {result['behaviors']} → behavior_log.jsonl")
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
