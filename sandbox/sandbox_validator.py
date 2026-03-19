"""Sandbox validator for candidate privacy rules.

This module is used by evolution_mechanic Step 5 as an offline gatekeeper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


ECOMMERCE_APPS = {"taobao", "tmall", "jd", "pinduoduo", "xianyu", "kaola"}


class SandboxValidator:
    """Validate whether a candidate rule conflicts with historical allow records."""

    def __init__(self, user_id: str, mode: str = "real", logs_root: str = "memory/logs") -> None:
        self.user_id = str(user_id)
        self.mode = str(mode).strip().lower() or "real"
        if self.mode not in {"real", "mock"}:
            raise ValueError(f"Unsupported sandbox mode: {mode}")
        self.logs_root = Path(logs_root)
        self._mock_allow_records: List[Dict[str, Any]] = []

    def set_mock_allow_records(self, rows: Iterable[Dict[str, Any]]) -> None:
        """Inject mock allow records for mode=mock."""
        self._mock_allow_records = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            self._mock_allow_records.append(
                {
                    "app_context": row.get("app_context"),
                    "action": row.get("action"),
                    "field": row.get("field"),
                }
            )

    def validate(self, candidate_rule: Dict[str, Any], correction_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a candidate rule and return structured verdict."""
        rule = dict(candidate_rule or {})

        if not self._is_valid_rule(rule):
            return {
                "passed": False,
                "rule": None,
                "narrowed": False,
                "original_scene": None,
                "conflict_details": [],
                "reason": "invalid_rule",
            }

        allow_records = self._load_allow_records()
        if not allow_records:
            return {
                "passed": True,
                "rule": rule,
                "narrowed": False,
                "original_scene": None,
                "conflict_details": [],
                "reason": "passed",
            }

        exclusion_list = self._build_exclusion_list(correction_batch)
        conflicts = self._check_conflict(rule, allow_records, exclusion_list)
        if not conflicts:
            return {
                "passed": True,
                "rule": rule,
                "narrowed": False,
                "original_scene": None,
                "conflict_details": [],
                "reason": "passed",
            }

        narrowed = self._narrow_scene(rule, conflicts)
        if not narrowed.get("_narrowed", False):
            narrowed.pop("_narrowed", None)
            return {
                "passed": False,
                "rule": rule,
                "narrowed": False,
                "original_scene": None,
                "conflict_details": conflicts,
                "reason": "rejected",
            }

        final_rule = dict(narrowed)
        final_rule.pop("_narrowed", None)
        post_conflicts = self._check_conflict(final_rule, allow_records, exclusion_list)
        if post_conflicts:
            return {
                "passed": False,
                "rule": rule,
                "narrowed": False,
                "original_scene": None,
                "conflict_details": post_conflicts,
                "reason": "rejected",
            }

        return {
            "passed": True,
            "rule": final_rule,
            "narrowed": True,
            "original_scene": str(rule.get("scene", "")),
            "conflict_details": [],
            "reason": "narrowed_passed",
        }

    def _load_allow_records(self) -> List[Dict[str, Any]]:
        if self.mode == "mock":
            return list(self._mock_allow_records)

        path = self.logs_root / self.user_id / "behavior_log.jsonl"
        if not path.exists():
            return []

        rows: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if str(item.get("resolution", "")).lower() != "allow":
                        continue
                    rows.append(
                        {
                            "app_context": item.get("app_context"),
                            "action": item.get("action"),
                            "field": item.get("field"),
                        }
                    )
        except Exception:
            return []
        return rows

    @staticmethod
    def _build_exclusion_list(correction_batch: List[Dict[str, Any]]) -> Set[str]:
        exclusion: Set[str] = set()
        for row in correction_batch:
            app_context = str(row.get("app_context", "")).strip()
            if app_context:
                exclusion.add(app_context)
        return exclusion

    def _check_conflict(
        self,
        rule: Dict[str, Any],
        allow_records: List[Dict[str, Any]],
        exclusion_list: Set[str],
    ) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        target_field = str(rule.get("sensitive_field", "")).strip().lower()

        for allow_row in allow_records:
            app_context = str(allow_row.get("app_context", "")).strip()
            if app_context in exclusion_list:
                continue

            allow_field = str(allow_row.get("field", "")).strip().lower()
            if not target_field or allow_field != target_field:
                continue

            if self._scene_covers(rule, app_context):
                conflicts.append(
                    {
                        "app_context": allow_row.get("app_context"),
                        "action": allow_row.get("action"),
                        "field": allow_row.get("field"),
                    }
                )

        return conflicts

    @staticmethod
    def _scene_covers(rule: Dict[str, Any], app_context: str) -> bool:
        hint = str(rule.get("app_context_hint", "")).strip().lower()
        scene = str(rule.get("scene", "")).strip().lower()
        app = str(app_context or "").strip().lower()
        if not app:
            return False

        if not hint:
            if "all" in scene or "any" in scene:
                hint = "all"
            elif "non_ecommerce" in scene or "non-ecommerce" in scene:
                hint = "non_ecommerce"
            elif "ecommerce" in scene:
                hint = "ecommerce"
            elif app in scene:
                hint = app

        if hint == "all":
            return True

        if hint == "non_ecommerce":
            return app not in ECOMMERCE_APPS

        if hint == "ecommerce":
            return app in ECOMMERCE_APPS

        if hint.startswith("except:"):
            excluded = hint.split(":", 1)[1].strip().lower()
            return bool(excluded) and app != excluded

        if hint == app:
            return True

        return False

    @staticmethod
    def _narrow_scene(rule: Dict[str, Any], conflict_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        conflict_apps = {
            str(item.get("app_context", "")).strip().lower() for item in conflict_details if item.get("app_context")
        }
        narrowed = dict(rule)
        narrowed["_narrowed"] = False

        if not conflict_apps:
            return narrowed

        if conflict_apps and conflict_apps.issubset(ECOMMERCE_APPS):
            narrowed["scene_narrowed"] = True
            narrowed["original_scene"] = str(rule.get("scene", ""))
            narrowed["scene"] = "non_ecommerce"
            narrowed["app_context_hint"] = "non_ecommerce"
            narrowed["narrowed_reason"] = "conflict_with_ecommerce_allow_history"
            narrowed["_narrowed"] = True
            return narrowed

        if len(conflict_apps) == 1:
            app = next(iter(conflict_apps))
            narrowed["scene_narrowed"] = True
            narrowed["original_scene"] = str(rule.get("scene", ""))
            narrowed["scene"] = f"except:{app}"
            narrowed["app_context_hint"] = f"except:{app}"
            narrowed["narrowed_reason"] = f"conflict_with_{app}_allow_history"
            narrowed["_narrowed"] = True
            return narrowed

        return narrowed

    @staticmethod
    def _is_valid_rule(rule: Dict[str, Any]) -> bool:
        confidence = float(rule.get("confidence", 0.0))
        if confidence < 0.6:
            return False

        rule_text = str(rule.get("rule_text", "")).strip()
        if not rule_text:
            return False

        strategy = str(rule.get("strategy", "")).strip().lower()
        if strategy not in {"block", "replace"}:
            return False

        if strategy == "replace" and not str(rule.get("replacement", "")).strip():
            return False

        scene = str(rule.get("scene", "")).strip()
        if not scene:
            return False

        # Guard against over-generic wording in v0.1.0.
        if scene in {"any", "all"}:
            return False

        return True
