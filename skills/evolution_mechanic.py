"""Evolution mechanic runtime pipeline.

Closed loop:
group -> score -> extract -> sandbox -> commit -> release
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from memory.chroma_manager import ChromaManager
from sandbox.sandbox_validator import SandboxValidator
from skill_registry.skill_db import SkillDB


VALID_CORRECTION_TYPES = {"user_denied", "user_modified", "user_interrupted"}


class SkillEvolution:
    """End-to-end evolution engine."""

    def __init__(
        self,
        *,
        logs_root: str = "memory/logs",
        memory_root: str = "memory",
        user_skills_root: str = "user_skills",
        prompt_template_path: str = "prompts/evolution_rule_extract.txt",
        skill_writing_template_path: str = "prompts/evolution_skill_writing.txt",
        sandbox_mode: str = "real",
        minicpm_url: str = "http://127.0.0.1:8000/chat",
        chroma_manager: Optional[ChromaManager] = None,
    ) -> None:
        self.logs_root = Path(logs_root)
        self.memory_root = Path(memory_root)
        self.user_skills_root = Path(user_skills_root)
        self.prompt_template_path = Path(prompt_template_path)
        self.skill_writing_template_path = Path(skill_writing_template_path)
        self.sandbox_mode = str(sandbox_mode).strip().lower() or "real"
        self.minicpm_url = minicpm_url
        self.chroma = chroma_manager or ChromaManager(storage_dir=str(self.memory_root / "chroma_storage"))
        self.skill_db = SkillDB(db_path=str(Path("skill_registry") / "skill_registry.db"))

        self.pending_file = self.memory_root / "candidate_rules_pending.jsonl"
        self.rejected_file = self.memory_root / "candidate_rules_rejected.jsonl"
        self._ensure_output_files()

    def _ensure_output_files(self) -> None:
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self.user_skills_root.mkdir(parents=True, exist_ok=True)
        for p in [self.pending_file, self.rejected_file]:
            if not p.exists():
                p.write_text("", encoding="utf-8")

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def correction_log_path(self, user_id: str) -> Path:
        return self.logs_root / user_id / "correction_log.jsonl"

    def behavior_log_path(self, user_id: str) -> Path:
        return self.logs_root / user_id / "behavior_log.jsonl"

    def load_correction_logs(self, user_id: str) -> List[Dict[str, Any]]:
        return self._read_jsonl(self.correction_log_path(user_id))

    def _is_expired(self, row: Dict[str, Any]) -> bool:
        expire_ts = row.get("expire_ts")
        if expire_ts is None:
            return False
        try:
            return int(expire_ts) < int(time.time())
        except Exception:
            return False

    def _is_valid_input_record(self, row: Dict[str, Any]) -> bool:
        # Must be unprocessed and non-expired.
        if bool(row.get("processed", False)):
            return False
        if self._is_expired(row):
            return False

        correction_type = str(row.get("correction_type", "")).strip()
        if correction_type not in VALID_CORRECTION_TYPES:
            return False

        # user_modified must be a real change.
        if correction_type == "user_modified":
            before = str(row.get("value_preview") or "").strip()
            after = str(row.get("correction_value") or "").strip()
            if before and after and before == after:
                return False

        return True

    def group_logs(
        self,
        rows: Sequence[Dict[str, Any]],
        *,
        min_support: int = 2,
    ) -> Dict[Tuple[str, str, str, str], List[Dict[str, Any]]]:
        grouped: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if not self._is_valid_input_record(row):
                continue
            user_id = str(row.get("user_id", "")).strip()
            action = str(row.get("action", "")).strip()
            app_context = str(row.get("app_context", "")).strip()
            field = str(row.get("field", "")).strip()
            if not user_id or not action:
                continue
            grouped[(user_id, action, app_context, field)].append(row)
        return {k: v for k, v in grouped.items() if len(v) >= min_support}

    @staticmethod
    def compute_confidence(group_rows: Sequence[Dict[str, Any]]) -> float:
        valid_rows = [
            r
            for r in group_rows
            if str(r.get("correction_type", "")) in ("user_modified", "user_interrupted")
            and str(r.get("correction_value") or "") != str(r.get("value_preview") or "")
        ]
        if len(valid_rows) < 2:
            return 0.0

        count_score = min(len(valid_rows) / 5.0, 1.0)

        values = [str(r.get("correction_value")) for r in valid_rows if r.get("correction_value")]
        if values:
            top = max(set(values), key=values.count)
            consistency_score = values.count(top) / len(values)
        else:
            consistency_score = 0.5

        interrupt_ratio = sum(
            1 for r in valid_rows if str(r.get("correction_type", "")) == "user_interrupted"
        ) / len(valid_rows)
        strength_score = 0.7 + 0.3 * interrupt_ratio

        validity_ratio = len(valid_rows) / len(group_rows) if group_rows else 0.0

        confidence = (
            count_score * 0.3
            + consistency_score * 0.3
            + strength_score * 0.2
            + validity_ratio * 0.2
        )
        return round(confidence, 2)

    def score_groups(
        self,
        groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]],
        *,
        threshold: float = 0.6,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        scored: List[Dict[str, Any]] = []
        pending: List[Dict[str, Any]] = []

        for (user_id, action, app_context, field), rows in groups.items():
            confidence = self.compute_confidence(rows)
            payload = {
                "user_id": user_id,
                "action": action,
                "app_context": app_context,
                "field": field,
                "confidence": confidence,
                "trigger_count": len(rows),
                "source_event_ids": [str(r.get("event_id", "")) for r in rows if r.get("event_id")],
                "examples": list(rows),
            }
            if confidence < threshold:
                payload["status"] = "pending"
                payload["reason"] = "low_confidence"
                pending.append(payload)
            else:
                scored.append(payload)

        return scored, pending

    @staticmethod
    def _build_examples_text(examples: Sequence[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, e in enumerate(examples, start=1):
            lines.extend(
                [
                    f"记录{i}：",
                    f"  场景：{e.get('app_context', '')}",
                    f"  Agent想做：{e.get('action', '')}，填入\"{e.get('value_preview', '')}\"",
                    f"  用户反应：{e.get('correction_type', '')}，改为\"{e.get('correction_value', '')}\"",
                ]
            )
        return "\n".join(lines)

    def _build_prompt(self, examples: Sequence[Dict[str, Any]]) -> str:
        if not self.prompt_template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {self.prompt_template_path}")

        template = self.prompt_template_path.read_text(encoding="utf-8")
        if "{examples}" not in template:
            raise ValueError("Prompt template missing {examples} placeholder")

        examples_text = self._build_examples_text(examples)
        return template.replace("{examples}", examples_text)

    def _build_skill_writing_prompt(self, rule: Dict[str, Any]) -> str:
        if not self.skill_writing_template_path.exists():
            raise FileNotFoundError(f"Skill writing template not found: {self.skill_writing_template_path}")

        template = self.skill_writing_template_path.read_text(encoding="utf-8")
        replacements = {
            "scene": str(rule.get("scene", "")),
            "sensitive_field": str(rule.get("sensitive_field", "")),
            "strategy": str(rule.get("strategy", "")),
            "rule_text": str(rule.get("rule_text", "")),
            "app_context_hint": str(rule.get("app_context_hint", "")),
            "replacement": "null" if rule.get("replacement") is None else str(rule.get("replacement", "")),
        }
        prompt = template
        for key, value in replacements.items():
            prompt = prompt.replace("{" + key + "}", value)
        return prompt

    @staticmethod
    def _is_valid_skill_body(body: str) -> bool:
        text = (body or "").strip()
        return (
            "## 何时使用" in text
            and "## 执行步骤" in text
            and "## 边界情况" in text
        )

    @staticmethod
    def _normalize_sensitive_field(model_field: str, fallback_field: str) -> str:
        # Keep a stable field identifier from logs when model output drifts
        # to semantic phrases like "Agent想做".
        fallback = str(fallback_field or "").strip()
        model = str(model_field or "").strip()
        if fallback:
            return fallback
        if not model:
            return ""
        low = model.lower()
        if low in {"agent想做", "action", "field", "content", "内容", "文本"}:
            return ""
        return model

    def _call_minicpm(self, prompt: str) -> str:
        data = urlparse.urlencode({"prompt": prompt}).encode("utf-8")
        req = urlrequest.Request(self.minicpm_url, data=data, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if str(payload.get("status")) != "success":
                    raise RuntimeError(str(payload.get("message", "MiniCPM error")))
                return str(payload.get("response", ""))
        except urlerror.URLError as exc:
            raise RuntimeError(f"MiniCPM request failed: {exc}") from exc

    @staticmethod
    def _extract_json_block(text: str) -> Dict[str, Any]:
        s = text.find("{")
        e = text.rfind("}")
        if s < 0 or e < 0 or e <= s:
            raise ValueError("No JSON object in model output")
        return json.loads(text[s : e + 1])

    # ========== Manifest & Catalog 管理 ==========

    @staticmethod
    def compute_content_hash(skill_dir: Path) -> str:
        """计算 Skill 内容哈希 = SKILL.md + rules.json 拼接后的 MD5"""
        hash_obj = hashlib.md5()
        for fname in sorted(["SKILL.md", "rules.json"]):
            fpath = skill_dir / fname
            if fpath.exists():
                hash_obj.update(fpath.read_bytes())
        return hash_obj.hexdigest()

    def _load_manifest(self, user_id: str) -> Dict[str, Any]:
        """加载用户的 manifest.json"""
        manifest_path = self.user_skills_root / user_id / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "user_id": user_id,
            "updated_at": int(time.time()),
            "skills": {}
        }

    def _save_manifest(self, user_id: str, manifest: Dict[str, Any]) -> None:
        """保存 manifest.json"""
        manifest_path = self.user_skills_root / user_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest["updated_at"] = int(time.time())
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_manifest_entry(self, user_id: str, skill_name: str, skill_dir: Path) -> None:
        """更新 manifest 中单个 Skill 的条目"""
        manifest = self._load_manifest(user_id)
        content_hash = self.compute_content_hash(skill_dir)

        # 从 rules.json 读取必要信息
        rules_path = skill_dir / "rules.json"
        confidence = 0.0
        version = "v0.1.0"
        if rules_path.exists():
            try:
                rules = json.loads(rules_path.read_text(encoding="utf-8"))
                confidence = float(rules.get("confidence", 0.0))
                version = str(rules.get("version", "v0.1.0"))
            except Exception:
                pass

        manifest["skills"][skill_name] = {
            "content_hash": content_hash,
            "version": version,
            "confidence": confidence,
        }
        self._save_manifest(user_id, manifest)

    def _remove_manifest_entry(self, user_id: str, skill_name: str) -> None:
        """从 manifest 中移除单个 Skill 条目"""
        manifest = self._load_manifest(user_id)
        if skill_name in manifest.get("skills", {}):
            del manifest["skills"][skill_name]
            self._save_manifest(user_id, manifest)

    def _update_skill_catalog(self, user_id: str) -> None:
        """重新生成 SKILL_CATALOG.md"""
        user_dir = self.user_skills_root / user_id
        catalog_path = user_dir / "SKILL_CATALOG.md"

        manifest = self._load_manifest(user_id)
        skills = manifest.get("skills", {})

        # 收集所有 Skill 的详细信息
        skill_entries: List[Dict[str, Any]] = []
        for skill_name, meta in skills.items():
            skill_dir = user_dir / skill_name
            rules_path = skill_dir / "rules.json"
            skill_info = {
                "name": skill_name,
                "content_hash": meta.get("content_hash", ""),
                "version": meta.get("version", "v0.1.0"),
                "confidence": meta.get("confidence", 0.0),
                "scene": "",
                "sensitive_field": "",
                "strategy": "",
                "app_context": "",
                "action": "",
            }
            if rules_path.exists():
                try:
                    rules = json.loads(rules_path.read_text(encoding="utf-8"))
                    skill_info.update({
                        "scene": rules.get("scene", ""),
                        "sensitive_field": rules.get("sensitive_field", ""),
                        "strategy": rules.get("strategy", ""),
                        "app_context": rules.get("app_context", ""),
                        "action": rules.get("action", ""),
                    })
                except Exception:
                    pass
            skill_entries.append(skill_info)

        # 构建 Markdown
        lines = [
            f"# {user_id} 的 Skills 目录\n",
            f"> 本文件描述该用户所有 Skills 的功能、适用场景和调用方式。\n",
            "> **客户端运行时应先加载此文件，了解如何正确调用。**\n",
            f"> 最后更新：{time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "\n## Skills 索引\n",
            "| Skill 名称 | 场景 | 敏感字段 | 策略 | 置信度 |\n",
            "|-----------|------|---------|------|--------|\n",
        ]

        for s in sorted(skill_entries, key=lambda x: x["name"]):
            scene = s.get("scene", "")[:30]
            field = s.get("sensitive_field", "")
            strategy = s.get("strategy", "")
            confidence = s.get("confidence", 0.0)
            lines.append(f"| `{s['name']}` | {scene} | {field} | {strategy} | {confidence:.0%} |\n")

        lines.append("\n## Skill 详情\n")
        for s in sorted(skill_entries, key=lambda x: x["name"]):
            lines.extend([
                f"\n### {s['name']}\n",
                f"\n**场景**：{s.get('scene', '未知')}\n",
                f"\n**敏感字段**：`{s.get('sensitive_field', '')}`\n",
                f"\n**策略**：`{s.get('strategy', '')}`\n",
                f"\n**应用上下文**：`{s.get('app_context', '')}`\n",
                f"\n**操作**：`{s.get('action', '')}`\n",
                f"\n**置信度**：{s.get('confidence', 0.0):.0%}\n",
                f"\n**内容哈希**：`{s.get('content_hash', '')}`\n",
            ])

        catalog_path.write_text("".join(lines), encoding="utf-8")

    def extract_rules(
        self,
        scored_groups: Sequence[Dict[str, Any]],
        *,
        max_examples: int = 5,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        rules: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for g in scored_groups:
            try:
                examples = list(g.get("examples", []))[:max_examples]
                prompt = self._build_prompt(examples)
                raw = self._call_minicpm(prompt)
                parsed = self._extract_json_block(raw)

                strategy = str(parsed.get("strategy", "")).strip().lower()
                replacement_raw = parsed.get("replacement")
                replacement_text = str(replacement_raw).strip() if replacement_raw is not None else ""
                replacement_is_empty = replacement_raw is None or replacement_text == "" or replacement_text.lower() == "none"

                if strategy not in {"block", "replace"}:
                    strategy = "replace" if not replacement_is_empty else "block"

                # Safety net: strategy=replace cannot carry empty replacement.
                if strategy == "replace" and replacement_is_empty:
                    strategy = "block"

                # Heuristic from behavior signals: only denied/interrupted without concrete replacement => block.
                has_modified_with_replacement = any(
                    str(e.get("correction_type", "")).strip() == "user_modified"
                    and str(e.get("correction_value") or "").strip() not in {"", "None", "none"}
                    for e in examples
                )
                if not has_modified_with_replacement and replacement_is_empty:
                    strategy = "block"

                replacement = None if strategy == "block" else replacement_raw

                confidence = float(g.get("confidence", 0.0))
                ts = int(time.time())
                user_id = str(g.get("user_id", ""))
                fallback_field = str(g.get("field", "")).strip()
                model_field = str(parsed.get("sensitive_field", "")).strip()
                app_context_hint = str(parsed.get("app_context_hint", "")).strip().lower()
                if not app_context_hint:
                    app_context_hint = str(g.get("app_context", "")).strip().lower() or "all"
                normalized_field = self._normalize_sensitive_field(model_field, fallback_field)
                rule = {
                    "rule_id": f"{user_id}_{ts}_{len(rules)+1:03d}",
                    "user_id": user_id,
                    "scene": str(parsed.get("scene", "")).strip(),
                    # Keep field identifiers stable and English for downstream matching and file naming.
                    "sensitive_field": normalized_field,
                    "model_sensitive_field": model_field,
                    "strategy": strategy,
                    "replacement": replacement,
                    "rule_text": str(parsed.get("rule_text", "")).strip(),
                    "app_context_hint": app_context_hint,
                    "confidence": confidence,
                    "trigger_count": int(g.get("trigger_count", 0)),
                    "needs_review": 0.6 <= confidence <= 0.75,
                    "status": "active",
                    "created_ts": ts,
                    "source_event_ids": list(g.get("source_event_ids", [])),
                    "source_examples": examples,
                    "app_context": str(g.get("app_context", "")),
                    "action": str(g.get("action", "")),
                    "field": fallback_field,
                }

                # Second model call: generate SKILL.md narrative body.
                skill_prompt = self._build_skill_writing_prompt(rule)
                skill_body_raw = self._call_minicpm(skill_prompt).strip()
                if not self._is_valid_skill_body(skill_body_raw):
                    raise ValueError("Invalid skill body generated by model")
                rule["skill_body"] = skill_body_raw

                rules.append(rule)
            except Exception as exc:
                errors.append(
                    {
                        "user_id": g.get("user_id", ""),
                        "action": g.get("action", ""),
                        "app_context": g.get("app_context", ""),
                        "error": str(exc),
                    }
                )

        return rules, errors

    @staticmethod
    def _build_mock_allow_records(input_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in input_rows:
            expected = str(item.get("expected_feedback", "")).strip().lower()
            if expected != "allow":
                continue
            rows.append(
                {
                    "app_context": item.get("app_context"),
                    "action": item.get("action"),
                    "field": item.get("field"),
                }
            )
        return rows

    def sandbox_validate(
        self,
        rules: Sequence[Dict[str, Any]],
        *,
        source_rows: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        approved: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        source_rows = list(source_rows or [])
        mock_allow_records = self._build_mock_allow_records(source_rows)

        for r in rules:
            user_id = str(r.get("user_id", ""))
            validator = SandboxValidator(user_id=user_id, mode=self.sandbox_mode, logs_root=str(self.logs_root))
            if self.sandbox_mode == "mock" and mock_allow_records:
                validator.set_mock_allow_records(mock_allow_records)

            result = validator.validate(
                candidate_rule=r,
                correction_batch=list(r.get("source_examples", [])),
            )

            if result.get("passed"):
                final_rule = dict(result.get("rule") or r)
                final_rule.pop("source_examples", None)
                approved.append(final_rule)
                continue

            reason = str(result.get("reason", "rejected"))
            conflict_details = list(result.get("conflict_details", []))
            rejected_row = {
                **r,
                "status": "rejected",
                "conflict_reason": reason,
                "conflict_details": conflict_details,
            }
            if reason == "invalid_rule":
                rejected_row["conflict_reason"] = "invalid_rule"
            rejected_row.pop("source_examples", None)
            rejected.append(rejected_row)

        return approved, rejected

    def commit_rules(self, rules: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        written: List[Dict[str, Any]] = []
        duplicates: List[Dict[str, Any]] = []

        for r in rules:
            rid = self.chroma.add_rule(str(r.get("user_id", "")), r)
            if rid:
                row = dict(r)
                row["rule_id"] = rid
                row["id"] = row.get("id") or rid
                written.append(row)
            else:
                duplicates.append({**r, "status": "rejected", "reason": "duplicate_or_write_failed"})

        return written, duplicates

    @staticmethod
    def _slugify(value: str) -> str:
        text = (value or "unknown").strip().lower().replace("_", "-").replace(" ", "-")
        text = re.sub(r"[^a-z0-9-]", "-", text)
        text = re.sub(r"-+", "-", text).strip("-")
        return text or "unknown"

    def _next_skill_version(self, user_id: str, base_name: str) -> int:
        root = self.user_skills_root / user_id
        if not root.exists():
            return 1
        prefix = f"{base_name}-v"
        max_v = 0
        for p in root.iterdir():
            if not p.is_dir() or not p.name.startswith(prefix):
                continue
            tail = p.name[len(prefix) :]
            try:
                max_v = max(max_v, int(tail))
            except ValueError:
                continue
        return max_v + 1

    def _write_skill_files(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        user_id = str(rule.get("user_id", "unknown"))
        field_slug = self._slugify(str(rule.get("sensitive_field", "field")))
        strategy_slug = self._slugify(str(rule.get("strategy", "replace")))
        base_name = f"privacy-{field_slug}-{strategy_slug}"
        version = self._next_skill_version(user_id, base_name)
        skill_name = f"{base_name}-v{version}"

        skill_dir = self.user_skills_root / user_id / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        confidence = float(rule.get("confidence", 0.0))
        needs_review = bool(rule.get("needs_review", False))
        created_ts = int(rule.get("created_ts", int(time.time())))
        skill_body = str(rule.get("skill_body", "")).strip()
        if not skill_body:
            raise ValueError("Missing skill_body in generated rule")

        skill_md = (
            "---\n"
            f"name: {skill_name}\n"
            "version: v0.1.0\n"
            "generated_by: skill-evolution-mechanic\n"
            f"generated_ts: {created_ts}\n"
            f"user_id: {user_id}\n"
            f"confidence: {confidence}\n"
            f"needs_review: {str(needs_review).lower()}\n"
            "status: sandbox_passed\n"
            "description: >\n"
            f"  在 {rule.get('scene', '')} 场景下保护 {rule.get('sensitive_field', '')} 字段。\n"
            f"  策略为 {rule.get('strategy', '')}。\n"
            "---\n\n"
            f"# {rule.get('scene', 'Privacy Rule')}\n\n"
            f"{skill_body}\n"
        )
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

        rule_copy = dict(rule)
        rule_copy["skill_path"] = str((self.user_skills_root / user_id / skill_name).as_posix())
        rule_copy["version"] = "v0.1.0"
        (skill_dir / "rules.json").write_text(
            json.dumps(rule_copy, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        version_tag = f"v{version}"
        self.skill_db.add_skill(
            user_id=user_id,
            skill_name=base_name,
            version=version_tag,
            path=str(skill_dir.as_posix()),
            rule_dict=rule_copy,
        )
        catalog_md = self.skill_db.generate_catalog_snapshot(user_id)
        catalog_path = self.user_skills_root / user_id / "SKILL_CATALOG.md"
        catalog_path.write_text(catalog_md, encoding="utf-8")

        return {
            "user_id": user_id,
            "skill_name": skill_name,
            "skill_path": str((self.user_skills_root / user_id / skill_name).as_posix()),
        }

    def release_user_skills(self, rules: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        released: List[Dict[str, Any]] = []
        for r in rules:
            released.append(self._write_skill_files(r))
        return released

    def mark_processed(self, user_id: str, event_ids: Sequence[str]) -> int:
        ids = {str(i) for i in event_ids if i}
        if not ids:
            return 0

        path = self.correction_log_path(user_id)
        rows = self._read_jsonl(path)
        changed = 0
        for row in rows:
            if str(row.get("event_id", "")) in ids and not bool(row.get("processed", False)):
                row["processed"] = True
                changed += 1
        self._write_jsonl(path, rows)
        return changed

    def _archive_pending(self, rows: Sequence[Dict[str, Any]]) -> None:
        for r in rows:
            self._append_jsonl(self.pending_file, {"created_ts": int(time.time()), "status": "pending", **r})

    def _archive_rejected(self, rows: Sequence[Dict[str, Any]]) -> None:
        for r in rows:
            self._append_jsonl(self.rejected_file, {"created_ts": int(time.time()), "status": "rejected", **r})

    def run_pipeline(
        self,
        *,
        user_id: str,
        step: str = "all",
        min_support: int = 2,
        threshold: float = 0.6,
        max_examples: int = 5,
        input_logs: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        step = step.lower().strip()
        allowed = {"group", "score", "extract", "sandbox", "commit", "release", "all"}
        if step not in allowed:
            raise ValueError(f"Unsupported step: {step}")

        rows = list(input_logs) if input_logs is not None else self.load_correction_logs(user_id)
        groups = self.group_logs(rows, min_support=min_support)

        if step == "group":
            return {
                "step": "group",
                "input_count": len(rows),
                "group_count": len(groups),
                "groups": [
                    {
                        "user_id": k[0],
                        "action": k[1],
                        "app_context": k[2],
                        "field": k[3],
                        "count": len(v),
                    }
                    for k, v in groups.items()
                ],
            }

        scored, pending = self.score_groups(groups, threshold=threshold)
        if step == "score":
            self._archive_pending(pending)
            return {
                "step": "score",
                "group_count": len(groups),
                "scored_count": len(scored),
                "pending_count": len(pending),
                "pending": pending,
            }

        extracted, extract_errors = self.extract_rules(scored, max_examples=max_examples)
        if step == "extract":
            self._archive_pending(pending)
            return {
                "step": "extract",
                "extracted_count": len(extracted),
                "extract_error_count": len(extract_errors),
                "pending_count": len(pending),
                "rules": extracted,
                "errors": extract_errors,
            }

        approved, rejected = self.sandbox_validate(extracted, source_rows=rows)
        if step == "sandbox":
            self._archive_pending(pending)
            self._archive_rejected(rejected)
            return {
                "step": "sandbox",
                "approved_count": len(approved),
                "rejected_count": len(rejected),
                "pending_count": len(pending),
                "rejected": rejected,
            }

        written, duplicates = self.commit_rules(approved)
        rejected_all = list(rejected) + list(duplicates)

        self._archive_pending(pending)
        self._archive_rejected(rejected_all)

        source_ids: List[str] = []
        for w in written:
            source_ids.extend(list(w.get("source_event_ids", [])))
        processed_count = self.mark_processed(user_id, source_ids)

        if step == "commit":
            return {
                "step": "commit",
                "input_count": len(rows),
                "group_count": len(groups),
                "scored_count": len(scored),
                "pending_count": len(pending),
                "extracted_count": len(extracted),
                "extract_error_count": len(extract_errors),
                "approved_count": len(approved),
                "written_count": len(written),
                "rejected_count": len(rejected_all),
                "processed_marked_count": processed_count,
                "written_rules": written,
                "rejected_rules": rejected_all,
                "errors": extract_errors,
            }

        released = self.release_user_skills(written)

        if step == "release":
            return {
                "step": "release",
                "released_count": len(released),
                "released": released,
                "written_count": len(written),
                "processed_marked_count": processed_count,
            }

        return {
            "step": "all",
            "input_count": len(rows),
            "group_count": len(groups),
            "scored_count": len(scored),
            "pending_count": len(pending),
            "extracted_count": len(extracted),
            "extract_error_count": len(extract_errors),
            "approved_count": len(approved),
            "written_count": len(written),
            "rejected_count": len(rejected_all),
            "processed_marked_count": processed_count,
            "written_rules": written,
            "released_count": len(released),
            "released": released,
            "rejected_rules": rejected_all,
            "errors": extract_errors,
        }