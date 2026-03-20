#!/usr/bin/env python3
"""Demo test runner for Evolution closed loop on P-GUI-Evo D1.

Flow:
1) Read D1 manifest and filter wechat subset.
2) Build behavior_log/correction_log under demo personas.
3) Check evolution trigger groups.
4) Run evolution pipeline with intermediate outputs.
5) Compare generated rules with gold rules.
6) Print final report.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.evolution_mechanic import SkillEvolution


VALID_CORRECTION = {"user_denied", "user_modified", "user_interrupted"}


@dataclass
class PersonaStats:
    persona: str
    trigger: bool = False
    generated_rules: int = 0
    strategy_correct: int = 0
    strategy_total: int = 0
    released_paths: List[str] = None

    def __post_init__(self) -> None:
        if self.released_paths is None:
            self.released_paths = []


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_app_context(entry: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(entry.get("app_platform", "")),
            str(entry.get("scenario_tag", "")),
            str(entry.get("agent_intent", "")),
        ]
    ).lower()
    if "wechat" in text or "微信" in text:
        return "wechat"
    if "taobao" in text or "淘宝" in text:
        return "taobao"
    if "jd" in text or "京东" in text:
        return "jd"
    if "his" in text or "医院" in text:
        return "hospital_his"
    if "forum" in text or "论坛" in text:
        return "forum"
    return "unknown_app"


def _infer_action(entry: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(entry.get("agent_intent", "")),
            str(entry.get("scenario_tag", "")),
        ]
    ).lower()
    if any(k in text for k in ["send", "发送", "转发", "分享"]):
        if any(k in text for k in ["file", "截图", "病历", "image", "图片", "report", "报告"]):
            return "send_file"
        return "send_message"
    if any(k in text for k in ["address", "住址", "地址"]):
        return "fill_home_address"
    if any(k in text for k in ["phone", "手机号", "电话"]):
        return "fill_phone"
    return "fill_form_field"


def _infer_field(entry: Dict[str, Any]) -> str:
    sim = entry.get("simulation_feedback") or {}
    rule = sim.get("rule_to_be_extracted") or {}
    trigger = rule.get("trigger") if isinstance(rule, dict) else {}
    if not isinstance(trigger, dict):
        trigger = {}
    pii_text = "|".join(
        [
            str(entry.get("pii_type", "")),
            "|".join(entry.get("pii_types_detected", []) or []),
            str(trigger.get("pii_type", "")),
        ]
    ).upper()
    if "HOME_ADDRESS" in pii_text or "ADDRESS" in pii_text:
        return "home_address"
    if "PHONE" in pii_text:
        return "phone"
    if "ID_CARD" in pii_text:
        return "id_card"
    if "MEDICAL" in pii_text or "RECORD" in pii_text:
        return "file_content"
    return "message_content"


def _map_resolution(expected_behavior: str) -> str:
    e = (expected_behavior or "").strip().lower()
    if e == "allow":
        return "allow"
    if e == "block":
        return "block"
    return "ask"


def _map_correction(entry: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    sim = entry.get("simulation_feedback") or {}
    user_action = str(sim.get("user_correction_action", "")).strip().lower()
    correction_value = str(entry.get("correction_value", "")).strip()

    if user_action in {"modify", "modified", "replace", "edit", "correct"} or correction_value:
        return "user_modified", correction_value or "user_provided_replacement"
    if user_action in {"reject", "denied", "deny", "block"}:
        return "user_denied", None
    if user_action in {"interrupt", "stop", "takeover", "take_over"}:
        return "user_interrupted", None

    # Accept means no correction signal.
    return None, None


def _build_logs(
    filtered_entries: List[Dict[str, Any]],
    logs_root: Path,
    demo_prefix: str,
) -> Tuple[
    Dict[str, int],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, str],
]:
    behavior_by_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    correction_by_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    gold_by_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    correction_type_counter: Counter[str] = Counter()
    event_to_scenario: Dict[str, str] = {}

    for i, entry in enumerate(filtered_entries, start=1):
        persona = str(entry.get("persona", "Unknown")).strip() or "Unknown"
        user_id = f"{demo_prefix}_{persona}"
        ts = int(time.time()) + i
        app_context = _normalize_app_context(entry)
        action = _infer_action(entry)
        field = _infer_field(entry)
        sim = entry.get("simulation_feedback") or {}
        expected_behavior = str(sim.get("expected_system_behavior", entry.get("expected_feedback", ""))).strip()
        resolution = _map_resolution(expected_behavior)

        event_id = f"{user_id}_{ts}_{i:04d}"
        event_to_scenario[event_id] = str(entry.get("scenario_tag", "")).strip()
        behavior_row = {
            "event_id": event_id,
            "user_id": user_id,
            "ts": ts,
            "app_context": app_context,
            "action": action,
            "field": field,
            "resolution": resolution,
            "level": 1,
            "processed": False,
            "expire_ts": ts + 7 * 24 * 3600,
        }
        behavior_by_user[user_id].append(behavior_row)

        correction_type, correction_value = _map_correction(entry)
        if correction_type in VALID_CORRECTION:
            correction_row = {
                "event_id": event_id,
                "user_id": user_id,
                "ts": ts,
                "app_context": app_context,
                "action": action,
                "field": field,
                "value_preview": str(entry.get("source_image_filename", "unknown_content")),
                "correction_type": correction_type,
                "correction_value": correction_value,
                "processed": False,
                "expire_ts": ts + 7 * 24 * 3600,
            }
            correction_by_user[user_id].append(correction_row)
            correction_type_counter[correction_type] += 1

        rule = (sim.get("rule_to_be_extracted") or {})
        if rule:
            gold_by_user[user_id].append(
                {
                    "action": str(rule.get("action", "")).strip().lower(),
                    "gold_rule": str(rule.get("gold_rule", "")).strip(),
                    "scenario_tag": str((rule.get("trigger") or {}).get("scenario_tag", "")).strip(),
                    "app_platform": str((rule.get("trigger") or {}).get("app_platform", "")).strip(),
                }
            )

    behavior_total = 0
    correction_total = 0
    for user_id, rows in behavior_by_user.items():
        path = logs_root / user_id / "behavior_log.jsonl"
        _write_jsonl(path, rows)
        behavior_total += len(rows)

    for user_id, rows in correction_by_user.items():
        path = logs_root / user_id / "correction_log.jsonl"
        _write_jsonl(path, rows)
        correction_total += len(rows)

    stats = {
        "behavior_total": behavior_total,
        "correction_total": correction_total,
        "correction_type_counter": dict(correction_type_counter),
        "persona_corrections": {k: len(v) for k, v in correction_by_user.items()},
    }
    return stats, behavior_by_user, correction_by_user, gold_by_user, event_to_scenario


def _build_mock_rule(group: Dict[str, Any]) -> Dict[str, Any]:
    examples = list(group.get("examples", []))
    user_id = str(group.get("user_id", "demo_user"))
    ts = int(time.time())

    replacements = [
        str(e.get("correction_value"))
        for e in examples
        if str(e.get("correction_type", "")) == "user_modified" and e.get("correction_value")
    ]
    strategy = "replace" if replacements else "block"
    replacement = Counter(replacements).most_common(1)[0][0] if replacements else None
    field = str(group.get("field", "message_content"))
    app_context = str(group.get("app_context", "all"))
    action = str(group.get("action", "fill_form_field"))

    skill_body = (
        "## 何时使用\n"
        f"当Agent在{app_context}场景执行{action}并涉及敏感内容时使用。\n\n"
        "## 执行步骤\n"
        "- [ ] 识别当前操作是否命中敏感场景。\n"
        + (
            "- [ ] 拦截本次操作并提示用户确认。\n"
            if strategy == "block"
            else f"- [ ] 将目标内容替换为{replacement}。\n"
        )
        + "- [ ] 记录处理结果并继续后续流程。\n\n"
        "## 边界情况\n"
        "- 用户未提供足够上下文：进入询问流程。\n"
        "- 字段不匹配：不触发此技能。"
    )

    return {
        "rule_id": f"{user_id}_{ts}_mock",
        "user_id": user_id,
        "scene": f"{app_context} {action}",
        "sensitive_field": field,
        "strategy": strategy,
        "replacement": replacement,
        "rule_text": f"在{app_context}场景处理{field}时执行{strategy}策略",
        "app_context_hint": app_context,
        "confidence": float(group.get("confidence", 0.7)),
        "trigger_count": int(group.get("trigger_count", 0)),
        "needs_review": False,
        "status": "active",
        "created_ts": ts,
        "source_event_ids": list(group.get("source_event_ids", [])),
        "source_examples": examples,
        "app_context": app_context,
        "action": action,
        "field": field,
        "skill_body": skill_body,
    }


def _strategy_to_expected(strategy: str) -> str:
    s = (strategy or "").strip().lower()
    if s == "block":
        return "block"
    if s == "replace":
        # In this pipeline, replace indicates privacy-preserving transformation,
        # and should be compared against gold "mask" behavior.
        return "mask"
    return "allow"


def _normalize_gold_action(action: str) -> str:
    a = (action or "").strip().lower()
    if a in {"block", "deny", "denied", "reject", "rejected"}:
        return "block"
    if a in {"mask", "masked", "redact", "redacted", "desensitize", "desensitized"}:
        return "mask"
    if a in {"allow", "allowed", "pass", "permit", "permitted"}:
        return "allow"
    return a or "unknown"


def _detect_rule_conflicts(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rules:
        key = (
            str(r.get("app_context_hint", "all")).strip().lower(),
            str(r.get("action", "")).strip().lower(),
            str(r.get("sensitive_field", "")).strip().lower(),
        )
        buckets[key].append(r)

    conflicts: List[Dict[str, Any]] = []
    for key, rows in buckets.items():
        if len(rows) < 2:
            continue
        strategies = {str(r.get("strategy", "")).strip().lower() for r in rows}
        replacements = {
            (None if r.get("replacement") is None else str(r.get("replacement", "")).strip())
            for r in rows
            if str(r.get("strategy", "")).strip().lower() == "replace"
        }
        if len(strategies) > 1 or len(replacements) > 1:
            conflicts.append(
                {
                    "scope": {
                        "app_context_hint": key[0],
                        "action": key[1],
                        "sensitive_field": key[2],
                    },
                    "rules": [
                        {
                            "rule_id": r.get("rule_id"),
                            "strategy": r.get("strategy"),
                            "replacement": r.get("replacement"),
                            "confidence": r.get("confidence"),
                        }
                        for r in rows
                    ],
                }
            )
    return conflicts


def _confidence_histogram(values: List[float]) -> Dict[str, int]:
    bins = {
        "<0.60": 0,
        "0.60-0.75": 0,
        "0.75-0.90": 0,
        ">=0.90": 0,
    }
    for v in values:
        if v < 0.60:
            bins["<0.60"] += 1
        elif v <= 0.75:
            bins["0.60-0.75"] += 1
        elif v < 0.90:
            bins["0.75-0.90"] += 1
        else:
            bins[">=0.90"] += 1
    return bins


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Evolution demo test on P-GUI-Evo D1")
    parser.add_argument("--dataset-root", default="/root/autodl-tmp/P-GUI-Evo-final/D1", help="D1 dataset root")
    parser.add_argument("--min-support", type=int, default=2, help="Min support for grouping")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence threshold")
    parser.add_argument("--max-samples", type=int, default=0, help="Limit samples after filtering (0 means all)")
    parser.add_argument("--demo-prefix", default="demo", help="Prefix for demo user ids (e.g. demo, demo2)")
    parser.add_argument("--wechat-only", action="store_true", help="Filter only wechat-related samples")
    parser.add_argument("--full-bucket", action="store_true", help="Use full D1 bucket without pass/shift filters")
    parser.add_argument("--analysis-only", action="store_true", help="Do not commit/release rules, only analyze outputs")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup demo logs and skills after run")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    dataset_root = Path(args.dataset_root)
    manifest_files = sorted(dataset_root.glob("manifest_index_final_server_step5_pruned_*.jsonl"))
    if not manifest_files:
        print("未找到 D1 manifest 文件，路径：", dataset_root)
        return 1

    manifest_path = manifest_files[0]
    print(f"使用数据文件: {manifest_path}")
    entries = _load_jsonl(manifest_path)

    filtered: List[Dict[str, Any]] = []
    for e in entries:
        if not args.full_bucket:
            if str(e.get("effective_quality_flag", "")).strip().lower() != "pass":
                continue
            shift = str(e.get("shift_type", "")).strip()
            if shift:
                continue
            sim = e.get("simulation_feedback")
            if not sim:
                continue
        if args.wechat_only:
            wechat_text = " ".join(
                [
                    str(e.get("app_platform", "")),
                    str(e.get("scenario_tag", "")),
                    str(e.get("agent_intent", "")),
                ]
            ).lower()
            if "微信" not in wechat_text and "wechat" not in wechat_text:
                continue
        filtered.append(e)

    if args.max_samples > 0:
        filtered = filtered[: args.max_samples]

    print(f"过滤后样本总数: {len(filtered)}")
    action_dist = Counter(str((e.get("simulation_feedback") or {}).get("user_correction_action", "Unknown")) for e in filtered)
    expected_dist = Counter(str((e.get("simulation_feedback") or {}).get("expected_system_behavior", "Unknown")) for e in filtered)
    print("user_correction_action 分布:", dict(action_dist))
    print("expected_system_behavior 分布:", dict(expected_dist))

    logs_root = project_root / "memory" / "logs"
    stats, _, correction_by_user, gold_by_user, event_to_scenario = _build_logs(filtered, logs_root, args.demo_prefix)

    print("\nStep 2 写入统计:")
    print("behavior_log 写入条数:", stats["behavior_total"])
    print("correction_log 写入条数:", stats["correction_total"])
    print("correction_type 分布:", stats["correction_type_counter"])
    print("各 persona correction 条数:", stats["persona_corrections"])

    print("\nStep 3 触发条件检查:")
    trigger_users: List[str] = []
    for user_id, rows in correction_by_user.items():
        groups = defaultdict(list)
        for r in rows:
            key = (str(r.get("action", "")), str(r.get("app_context", "")), str(r.get("field", "")))
            groups[key].append(r)
        sat = {k: len(v) for k, v in groups.items() if len(v) >= args.min_support}
        if sat:
            trigger_users.append(user_id)
            print(f"{user_id} 满足触发分组: {sat}")
        else:
            print(f"{user_id} 无可触发分组，原因: 每组条数 < {args.min_support}")

    if not trigger_users:
        print("\n报警：当前数据不足以触发 Evolution")
        print("建议：降低 --min-support 到 1 或扩大数据范围")

    persona_results: Dict[str, PersonaStats] = {}
    generated_rules_by_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    print("\nStep 4 触发 Evolution:")
    for user_id in sorted(set(list(correction_by_user.keys()) + list(trigger_users))):
        persona_results[user_id] = PersonaStats(persona=user_id)

    for user_id in trigger_users:
        print(f"\n--- Persona {user_id} ---")
        engine = SkillEvolution(
            logs_root=str(logs_root),
            memory_root=str(project_root / "memory"),
            user_skills_root=str(project_root / "user_skills"),
            sandbox_mode="real",
        )
        persona_results[user_id].trigger = True

        rows = engine.load_correction_logs(user_id)
        groups = engine.group_logs(rows, min_support=args.min_support)
        print("Step 1 分组结果:", {str(k): len(v) for k, v in groups.items()})

        scored, pending = engine.score_groups(groups, threshold=args.threshold)
        print("Step 2 confidence:", [
            {
                "action": g.get("action"),
                "app_context": g.get("app_context"),
                "field": g.get("field"),
                "confidence": g.get("confidence"),
                "trigger_count": g.get("trigger_count"),
            }
            for g in scored
        ])
        if pending:
            print("Step 2 pending:", pending)

        raw_outputs: List[str] = []
        original_call = engine._call_minicpm

        def _wrapped_call(prompt: str) -> str:
            resp = original_call(prompt)
            raw_outputs.append(resp)
            return resp

        engine._call_minicpm = _wrapped_call
        extracted, errors = engine.extract_rules(scored, max_examples=5)
        engine._call_minicpm = original_call

        print("Step 3 MiniCPM 原始输出条数:", len(raw_outputs))
        for idx, out in enumerate(raw_outputs, start=1):
            print(f"MiniCPM[{idx}] 原始输出:\n{out}\n")

        if errors:
            print("Step 3 报错:", errors)
            if extracted:
                print("Step 3 部分提炼成功，继续后续流程")
            else:
                print("Step 3 全部失败，使用 mock 规则继续测试")
                extracted = [_build_mock_rule(g) for g in scored]

        approved, rejected = engine.sandbox_validate(extracted, source_rows=rows)
        print("Step 5 沙盒结果: approved=", len(approved), "rejected=", len(rejected))
        if rejected:
            print("rejected 详情:", rejected)

        for r in approved:
            generated_rules_by_user[user_id].append(r)

        if args.analysis_only:
            print("Step 6 写入路径: [analysis_only 模式，跳过 commit/release]")
            persona_results[user_id].generated_rules = len(approved)
            print("processed 标记条数: 0 (analysis_only)")
        else:
            written, duplicates = engine.commit_rules(approved)
            if duplicates:
                print("Step 5 写入冲突(重复/失败):", duplicates)

            source_ids: List[str] = []
            for w in written:
                source_ids.extend(list(w.get("source_event_ids", [])))
            processed_count = engine.mark_processed(user_id, source_ids)

            released = engine.release_user_skills(written)
            print("Step 6 写入路径:", released)

            persona_results[user_id].generated_rules = len(written)
            persona_results[user_id].released_paths = [r.get("skill_path", "") for r in released]
            generated_rules_by_user[user_id] = written

            for item in released:
                skill_file = project_root / item["skill_path"] / "SKILL.md"
                if skill_file.exists():
                    content = skill_file.read_text(encoding="utf-8")
                    print(f"生成的 Skill 文件: {skill_file}")
                    print(content[:1200])

            print(f"processed 标记条数: {processed_count}")

    print("\nStep 5 质量评估:")
    for user_id, rules in generated_rules_by_user.items():
        gold_rules = gold_by_user.get(user_id, [])
        for i, rule in enumerate(rules, start=1):
            expected_action = "unknown"
            gold_rule_text = ""
            scenario_tag = ""
            if gold_rules:
                g = gold_rules[min(i - 1, len(gold_rules) - 1)]
                expected_action = _normalize_gold_action(g.get("action", "unknown"))
                gold_rule_text = g.get("gold_rule", "")
                scenario_tag = g.get("scenario_tag", "")

            pred_action = _strategy_to_expected(str(rule.get("strategy", "")))
            strategy_ok = pred_action == expected_action
            if expected_action != "unknown":
                persona_results[user_id].strategy_total += 1
                persona_results[user_id].strategy_correct += 1 if strategy_ok else 0

            app_hint = str(rule.get("app_context_hint", "")).lower()
            scene_match = app_hint in scenario_tag.lower() or app_hint in str(rule.get("scene", "")).lower()

            print(f"规则{i} ({user_id})")
            print("  生成strategy:", rule.get("strategy"), "=>", pred_action)
            print("  期望action:", expected_action, "| strategy:", "✅" if strategy_ok else "❌")
            print("  生成rule_text:", rule.get("rule_text"))
            print("  gold_rule:", gold_rule_text)
            print("  场景匹配:", "✅" if scene_match else "❌")

    # Coverage and confidence analysis.
    all_scenarios: Set[str] = set()
    for user_id, rows in gold_by_user.items():
        if user_id not in persona_results:
            continue
        for r in rows:
            tag = str(r.get("scenario_tag", "")).strip()
            if tag:
                all_scenarios.add(tag)

    covered_scenarios: Set[str] = set()
    for _, rules in generated_rules_by_user.items():
        for rule in rules:
            for sid in rule.get("source_event_ids", []) or []:
                tag = event_to_scenario.get(str(sid), "")
                if tag:
                    covered_scenarios.add(tag)

    missed_scenarios = sorted(all_scenarios - covered_scenarios)
    covered_scenarios_sorted = sorted(covered_scenarios)

    confidence_values = [float(r.get("confidence", 0.0)) for rs in generated_rules_by_user.values() for r in rs]
    confidence_hist = _confidence_histogram(confidence_values)

    user_conflicts: Dict[str, List[Dict[str, Any]]] = {}
    for uid in [k for k in persona_results.keys() if ("UserA" in k or "UserB" in k)]:
        user_conflicts[uid] = _detect_rule_conflicts(generated_rules_by_user.get(uid, []))

    print("\n========= Evolution Demo 测试报告 =========")
    print("数据集子集：D1 微信场景")
    print("样本总数：", len(filtered), "条")
    print("有效 correction 信号：", stats["correction_total"], "条")

    print("\n各 Persona 结果：")
    for user_id, result in sorted(persona_results.items()):
        acc = (
            f"{result.strategy_correct}/{result.strategy_total}"
            if result.strategy_total > 0
            else "N/A"
        )
        print(f"  {user_id}:")
        print("    触发 Evolution：", "是" if result.trigger else "否")
        print("    生成规则数：", result.generated_rules)
        print("    strategy 正确率：", acc)

    print("\n生成的 Skill 路径：")
    for user_id, result in sorted(persona_results.items()):
        for path in result.released_paths:
            print(" ", path)

    print("\n========= UserA/UserB 规则冲突检查 =========")
    for uid in sorted(user_conflicts.keys()):
        rs = generated_rules_by_user.get(uid, [])
        print(f"{uid}: 规则数={len(rs)}")
        if user_conflicts[uid]:
            print("  冲突: 是")
            for c in user_conflicts[uid]:
                print("  冲突范围:", c["scope"]) 
                print("  规则详情:", c["rules"]) 
        else:
            print("  冲突: 否")

    print("\n========= 覆盖矩阵分析 =========")
    print("覆盖场景数:", len(covered_scenarios_sorted))
    print("覆盖场景:", covered_scenarios_sorted)
    print("漏掉场景数:", len(missed_scenarios))
    print("漏掉场景:", missed_scenarios)

    print("\n========= Confidence 分布 =========")
    print("规则数量:", len(confidence_values))
    if confidence_values:
        print("min/max/avg:", round(min(confidence_values), 3), round(max(confidence_values), 3), round(sum(confidence_values) / len(confidence_values), 3))
    print("histogram:", confidence_hist)

    print("==========================================")

    if args.cleanup:
        for user_id in list(correction_by_user.keys()):
            log_dir = logs_root / user_id
            if log_dir.exists():
                for p in log_dir.glob("*"):
                    p.unlink(missing_ok=True)
                log_dir.rmdir()
        for user_id in list(correction_by_user.keys()):
            skill_dir = project_root / "user_skills" / user_id
            if skill_dir.exists():
                for p in sorted(skill_dir.rglob("*"), reverse=True):
                    if p.is_file():
                        p.unlink(missing_ok=True)
                    elif p.is_dir():
                        p.rmdir()
                if skill_dir.exists():
                    skill_dir.rmdir()
        print("已清理 demo 数据")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
