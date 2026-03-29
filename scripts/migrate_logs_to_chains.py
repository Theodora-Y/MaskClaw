#!/usr/bin/env python3
"""历史日志迁移工具 - 将旧格式聚类生成新的 session_trace.jsonl

使用方法:
    python scripts/migrate_logs_to_chains.py [--user USER_ID] [--logs-root PATH] [--dry-run]

功能:
    1. 读取用户的 behavior_log.jsonl 和 correction_log.jsonl
    2. 根据 _scenario_tag (或 _parent_entry_id) 聚类
    3. 生成新的 session_trace.jsonl
    4. 可选：将聚类结果保存到 skill_db
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """读取 JSONL 文件。"""
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
                    print(f"  [WARN] 跳过无效 JSON 行: {line[:50]}...")
    return rows


def extract_scenario_tag(item: Dict[str, Any]) -> str:
    """提取场景标签。"""
    return str(
        item.get("_scenario_tag") or
        item.get("_parent_entry_id") or
        item.get("scenario_tag") or
        "unknown"
    )


def build_action_record(item: Dict[str, Any], action_index: int) -> Dict[str, Any]:
    """从旧格式构建新的动作记录。"""
    # correction_log 条目没有 resolution，需要推断
    resolution = item.get("resolution")
    if resolution is None:
        # correction 条目：被拦截
        if item.get("correction_type"):
            resolution = "blocked"
        else:
            resolution = "unknown"

    return {
        "action_index": action_index,
        "ts": item.get("ts", 0),
        "action": item.get("action", "unknown"),
        "field": item.get("field"),
        "resolution": resolution,
        "value_preview": item.get("value_preview"),
        "is_correction": bool(item.get("correction_type")),
        "correction_type": item.get("correction_type"),
        "correction_value": item.get("correction_value"),
        "pii_type": item.get("_pii_type") or item.get("pii_types_involved"),
        "relationship_tag": item.get("_relationship_tag"),
        "agent_intent": item.get("_agent_intent"),
        "quality_score": item.get("_quality_score"),
        "quality_flag": item.get("_quality_flag"),
    }


def migrate_user_logs(
    user_id: str,
    logs_root: str = "memory/logs",
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """迁移单个用户的日志。"""
    logs_path = Path(logs_root)
    user_dir = logs_path / user_id

    if not user_dir.exists():
        return {
            "user_id": user_id,
            "success": False,
            "error": f"用户目录不存在: {user_dir}",
        }

    behavior_path = user_dir / "behavior_log.jsonl"
    correction_path = user_dir / "correction_log.jsonl"

    if not behavior_path.exists() and not correction_path.exists():
        return {
            "user_id": user_id,
            "success": False,
            "error": f"没有找到日志文件: {user_dir}",
        }

    # 读取日志
    behaviors = read_jsonl(behavior_path)
    corrections = read_jsonl(correction_path)

    print(f"  读取 behavior_log: {len(behaviors)} 条")
    print(f"  读取 correction_log: {len(corrections)} 条")

    # 按场景聚类
    scenario_map: Dict[str, Dict[str, List]] = {}

    # 合并两个日志：用 event_id 去重，但合并元数据
    # 同一 event_id 可能同时存在于 behavior_log 和 correction_log
    merged_events: Dict[str, Dict[str, Any]] = {}

    for item in behaviors + corrections:
        event_id = item.get("event_id", "")
        if not event_id:
            continue

        if event_id not in merged_events:
            merged_events[event_id] = item.copy()
        else:
            # 合并元数据
            existing = merged_events[event_id]
            # 保留 correction_type（来自 correction_log）
            if not existing.get("correction_type") and item.get("correction_type"):
                existing["correction_type"] = item["correction_type"]
            # 保留 correction_value
            if not existing.get("correction_value") and item.get("correction_value"):
                existing["correction_value"] = item["correction_value"]
            # 保留其他 _ 开头的元数据
            for key, value in item.items():
                if key.startswith("_") and not existing.get(key):
                    existing[key] = value

    # 转换为列表
    all_items = list(merged_events.values())

    for item in all_items:
        scenario_tag = extract_scenario_tag(item)
        if scenario_tag not in scenario_map:
            scenario_map[scenario_tag] = {"behaviors": [], "corrections": []}

        if item.get("correction_type"):
            scenario_map[scenario_tag]["corrections"].append(item)
        else:
            scenario_map[scenario_tag]["behaviors"].append(item)

    print(f"  聚类生成 {len(scenario_map)} 个行为链")

    # 构建行为链
    chains = []
    skipped_corrections = 0

    for scenario_tag, data in scenario_map.items():
        if not data["corrections"]:
            skipped_corrections += 1
            continue

        all_actions = data["behaviors"] + data["corrections"]
        all_actions.sort(key=lambda x: x.get("ts", 0))

        timestamps = [a.get("ts", 0) for a in all_actions if a.get("ts")]
        start_ts = min(timestamps) if timestamps else 0
        end_ts = max(timestamps) if timestamps else 0

        chain_id = f"{user_id}_{scenario_tag}_{start_ts}"

        # 提取 app_context, rule_type, final_resolution
        app_context = "unknown"
        rule_type = "N"
        final_resolution = "unknown"
        for item in data["corrections"] + data["behaviors"]:
            if item.get("app_context") and item["app_context"] != "unknown":
                app_context = item["app_context"]
            if item.get("_rule_type"):
                rule_type = item["_rule_type"]
            # final_resolution: 优先使用 behavior_log 的 resolution
            res = item.get("resolution")
            if res is not None:
                final_resolution = res

        # 构建链内动作
        actions = []
        for i, item in enumerate(all_actions):
            act = build_action_record(item, i)
            actions.append({k: v for k, v in act.items() if v is not None})

        chain = {
            "chain_id": chain_id,
            "user_id": user_id,
            "app_context": app_context,
            "scenario_tag": scenario_tag,
            "rule_type": rule_type,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "action_count": len(actions),
            "has_correction": len(data["corrections"]) > 0,
            "correction_count": len(data["corrections"]),
            "final_resolution": final_resolution,
            "processed": False,
            "actions": actions,
        }

        chains.append(chain)

    print(f"  生成 {len(chains)} 条有效行为链 (跳过无纠错的场景: {skipped_corrections})")

    # 写入新格式
    if output_dir:
        trace_path = output_dir / "session_trace.jsonl"
    else:
        trace_path = user_dir / "session_trace.jsonl"

    if not dry_run:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("w", encoding="utf-8") as f:
            for chain in chains:
                f.write(json.dumps(chain, ensure_ascii=False) + "\n")
        print(f"  写入: {trace_path}")
    else:
        print(f"  [DRY-RUN] 模拟写入: {trace_path}")

    # 统计
    stats = {
        "user_id": user_id,
        "success": True,
        "behavior_count": len(behaviors),
        "correction_count": len(corrections),
        "scenario_count": len(scenario_map),
        "chain_count": len(chains),
        "skipped_count": skipped_corrections,
        "output_path": str(trace_path),
    }

    return stats


def list_users(logs_root: str) -> List[str]:
    """列出日志目录下的所有用户。"""
    logs_path = Path(logs_root)
    if not logs_path.exists():
        return []

    users = []
    for user_dir in logs_path.iterdir():
        if user_dir.is_dir():
            behavior_file = user_dir / "behavior_log.jsonl"
            correction_file = user_dir / "correction_log.jsonl"
            if behavior_file.exists() or correction_file.exists():
                users.append(user_dir.name)
    return users


def main():
    parser = argparse.ArgumentParser(
        description="历史日志迁移工具 - 将旧格式聚类生成 session_trace.jsonl"
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="指定用户ID，不指定则处理所有用户",
    )
    parser.add_argument(
        "--logs-root",
        type=str,
        default="memory/logs",
        help="日志根目录 (默认: memory/logs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="输出目录 (默认: 与输入相同目录)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅模拟，不写入文件",
    )
    parser.add_argument(
        "--list-users",
        action="store_true",
        help="列出所有可迁移的用户",
    )

    args = parser.parse_args()

    # 处理输出目录
    output_dir = Path(args.output_dir) if args.output_dir else None

    # 列出用户
    if args.list_users:
        users = list_users(args.logs_root)
        print(f"可迁移的用户 ({len(users)}):")
        for u in users:
            print(f"  - {u}")
        return

    # 确定要处理的用户
    if args.user:
        users = [args.user]
    else:
        users = list_users(args.logs_root)

    if not users:
        print("没有找到可迁移的用户")
        return

    print("=" * 60)
    print("历史日志迁移工具 v2.0")
    print("=" * 60)
    print(f"日志目录: {args.logs_root}")
    print(f"输出目录: {output_dir or '(原目录)'}")
    print(f"用户数量: {len(users)}")
    print(f"模拟运行: {args.dry_run}")
    print("=" * 60)

    total_stats = {
        "total_users": len(users),
        "success_count": 0,
        "error_count": 0,
        "total_chains": 0,
    }

    for user in users:
        print(f"\n>>> 处理用户: {user}")
        try:
            stats = migrate_user_logs(
                user_id=user,
                logs_root=args.logs_root,
                output_dir=output_dir,
                dry_run=args.dry_run,
            )
            if stats.get("success"):
                total_stats["success_count"] += 1
                total_stats["total_chains"] += stats.get("chain_count", 0)
            else:
                total_stats["error_count"] += 1
                print(f"  [ERROR] {stats.get('error', '未知错误')}")
        except Exception as e:
            total_stats["error_count"] += 1
            print(f"  [ERROR] {e}")
            if args.dry_run:
                import traceback
                traceback.print_exc()

    print("\n" + "=" * 60)
    print("迁移完成")
    print("=" * 60)
    print(f"成功: {total_stats['success_count']}/{total_stats['total_users']}")
    print(f"错误: {total_stats['error_count']}")
    print(f"生成行为链: {total_stats['total_chains']}")


if __name__ == "__main__":
    main()
