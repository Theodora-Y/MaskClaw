from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from maskclaw_cli.context import PROJECT_ROOT


APP_NAMES = {
    "wechat": "微信",
    "jd": "京东",
    "taobao": "淘宝",
    "alipay": "支付宝",
    "dingtalk": "钉钉",
    "feishu": "飞书",
    "his": "HIS系统",
    "unknown_app": "未知应用",
}
ACTION_NAMES = {
    "send_file": "发送文件",
    "fill_home_address": "填写家庭住址",
    "fill_form_field": "填写表单",
    "send_message": "发送消息",
    "upload_file": "上传文件",
    "share_content": "分享内容",
}
CORRECTION_NAMES = {
    "user_denied": "拒绝了这个操作",
    "user_modified": "将内容修改为自定义替代值",
    "user_approved": "手动放行了这个操作",
    "user_blocked": "手动拦截了这个操作",
}


class LocalLogService:
    """Read audit timelines and raw logs directly from local files/SQLite."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.memory_root = self.project_root / "memory" / "logs"
        self.skill_db_path = self.project_root / "skill_registry" / "skill_registry.db"

    def recent(
        self,
        user_id: str,
        source: str = "timeline",
        event_type: str | None = None,
        log_type: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if source == "raw":
            logs, total = self._read_raw_logs(user_id, log_type=log_type, page=page, page_size=page_size)
            payload = {
                "user_id": user_id,
                "log_type": log_type,
                "logs": logs,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "has_next": page * page_size < total,
                },
                "transport": "local",
            }
            return payload

        events = self._build_correction_events(user_id)
        events.extend(self._build_publish_events(user_id))
        if event_type:
            events = [event for event in events if str(event.get("event_type")) == event_type]
        events.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
        total = len(events)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = events[start_idx:end_idx]
        return {
            "user_id": user_id,
            "range": "all",
            "filters": {
                "event_types": [event_type] if event_type else sorted({str(item.get("event_type")) for item in events}),
                "from_ts": None,
                "to_ts": None,
            },
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": end_idx < total,
            },
            "groups": self._group_events_by_date(page_items),
            "transport": "local",
        }

    def tail(
        self,
        user_id: str,
        log_type: str = "all",
        limit: int = 10,
    ) -> dict[str, Any]:
        logs, total = self._read_raw_logs(user_id, log_type=log_type, page=1, page_size=limit)
        return {
            "user_id": user_id,
            "log_type": log_type,
            "logs": logs,
            "pagination": {
                "page": 1,
                "page_size": limit,
                "total": total,
                "has_next": total > limit,
            },
            "transport": "local",
        }

    def _connect_skill_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.skill_db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _read_raw_logs(
        self,
        user_id: str,
        log_type: str,
        page: int,
        page_size: int,
    ) -> tuple[dict[str, list[dict[str, Any]]], int]:
        mapping = {
            "correction": ["correction_log.jsonl"],
            "behavior": ["behavior_log.jsonl"],
            "session_trace": ["session_trace.jsonl"],
            "all": ["correction_log.jsonl", "behavior_log.jsonl", "session_trace.jsonl"],
        }
        targets = mapping[log_type]
        root = self.memory_root / user_id
        payload: dict[str, list[dict[str, Any]]] = {}
        total = 0
        for name in targets:
            records = self._read_jsonl_records(root / name, limit=None)
            total += len(records)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            payload[name] = records[start_idx:end_idx]
        return payload, total

    def _read_jsonl_records(self, path: Path, limit: int | None) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except Exception:
                    continue
                ts = int(raw.get("ts") or raw.get("timestamp") or 0)
                rows.append({"line_no": line_no, "ts": ts, "raw": raw})
        rows.sort(key=lambda item: int(item.get("ts") or 0), reverse=True)
        return rows[:limit] if limit is not None else rows

    def _build_correction_events(self, user_id: str) -> list[dict[str, Any]]:
        path = self.memory_root / user_id / "correction_log.jsonl"
        if not path.exists():
            return []

        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except Exception:
                    continue

                ts = int(raw.get("ts") or 0)
                if ts <= 0:
                    continue

                correction_type = str(raw.get("correction_type") or "")
                if correction_type in {"user_denied", "user_blocked"}:
                    event_type = "conflict"
                    type_label = "规则冲突"
                    conflict_note = "用户拒绝或拦截，需重新确认规则边界"
                elif correction_type == "user_modified":
                    event_type = "added"
                    type_label = "规则新增"
                    conflict_note = None
                else:
                    event_type = "reinforced"
                    type_label = "规则强化"
                    conflict_note = None

                app = APP_NAMES.get(str(raw.get("app_context") or ""), str(raw.get("app_context") or "未知应用"))
                title = f"{app}{type_label}"
                events.append(
                    {
                        "event_id": str(raw.get("event_id") or f"corr-{user_id}-{line_no}"),
                        "ts": ts,
                        "date_key": self._date_key(ts),
                        "event_type": event_type,
                        "type_label": type_label,
                        "skill_name": None,
                        "title": title,
                        "summary": self._event_to_summary(raw),
                        "source": "用户纠错",
                        "trigger_delta": 1 if event_type == "reinforced" else 0,
                        "conflict_note": conflict_note,
                        "action_label": "查看详情" if event_type != "conflict" else "解决冲突",
                        "action_target": {
                            "kind": "correction_log",
                            "event_id": str(raw.get("event_id") or ""),
                        },
                        "processed": bool(raw.get("processed", False)),
                        "source_ref": f"correction_log.jsonl:{line_no}",
                    }
                )
        return events

    def _build_publish_events(self, user_id: str) -> list[dict[str, Any]]:
        if not self.skill_db_path.exists():
            return []

        events: list[dict[str, Any]] = []
        with self._connect_skill_db() as conn:
            rows = conn.execute(
                """
                SELECT id, skill_name, version, scene, rule_text, created_ts
                FROM skills
                WHERE user_id = ? AND status = 'active'
                ORDER BY COALESCE(updated_ts, created_ts) DESC
                """,
                (user_id,),
            ).fetchall()
            first_rows = conn.execute(
                """
                SELECT skill_name, MIN(created_ts) AS first_ts
                FROM skills
                WHERE user_id = ? AND status = 'active'
                GROUP BY skill_name
                """,
                (user_id,),
            ).fetchall()
            archived_rows = conn.execute(
                """
                SELECT id, skill_name, version, scene, archived_ts, archived_reason
                FROM skills
                WHERE user_id = ? AND status = 'archived' AND archived_ts IS NOT NULL
                ORDER BY archived_ts DESC
                """,
                (user_id,),
            ).fetchall()

        first_version_map = {str(row["skill_name"]): int(row["first_ts"] or 0) for row in first_rows}

        for row in rows:
            ts = int(row["created_ts"] or 0)
            if ts <= 0:
                continue

            skill_name = str(row["skill_name"] or "unknown-skill")
            version = str(row["version"] or "")
            is_first = int(first_version_map.get(skill_name, 0)) == ts
            event_type = "added" if is_first else "reinforced"
            type_label = "规则新增" if is_first else "规则强化"
            scene = str(row["scene"] or skill_name)
            events.append(
                {
                    "event_id": f"skill-{row['id']}",
                    "ts": ts,
                    "date_key": self._date_key(ts),
                    "event_type": event_type,
                    "type_label": type_label,
                    "skill_name": skill_name,
                    "title": f"{scene} {type_label}",
                    "summary": f"系统发布了 {skill_name} {version}",
                    "source": "自动推导",
                    "trigger_delta": 0 if is_first else 1,
                    "conflict_note": None,
                    "action_label": "查看详情",
                    "action_target": {
                        "kind": "skill_version",
                        "skill_name": skill_name,
                        "version": version,
                    },
                    "processed": True,
                    "source_ref": f"skills:{row['id']}",
                }
            )

        for row in archived_rows:
            ts = int(row["archived_ts"] or 0)
            if ts <= 0:
                continue
            skill_name = str(row["skill_name"] or "unknown-skill")
            version = str(row["version"] or "")
            scene = str(row["scene"] or skill_name)
            reason = str(row["archived_reason"] or "策略停用")
            events.append(
                {
                    "event_id": f"arch-{row['id']}",
                    "ts": ts,
                    "date_key": self._date_key(ts),
                    "event_type": "disabled",
                    "type_label": "规则停用",
                    "skill_name": skill_name,
                    "title": f"{scene} 规则停用",
                    "summary": f"{skill_name} {version} 已停用，原因：{reason}",
                    "source": "自动推导",
                    "trigger_delta": 0,
                    "conflict_note": None,
                    "action_label": "查看详情",
                    "action_target": {
                        "kind": "archived_skill",
                        "skill_name": skill_name,
                        "version": version,
                    },
                    "processed": True,
                    "source_ref": f"skills:{row['id']}",
                }
            )
        return events

    def _group_events_by_date(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            key = str(event.get("date_key") or "未知日期")
            grouped.setdefault(key, []).append(event)

        def _sort_key(key: str) -> int:
            try:
                normalized = key.replace("年", "-").replace("月", "-").replace("日", "")
                return int(datetime.strptime(normalized, "%Y-%m-%d").timestamp())
            except Exception:
                return 0

        groups = []
        for key in sorted(grouped, key=_sort_key, reverse=True):
            items = sorted(grouped[key], key=lambda item: int(item.get("ts") or 0), reverse=True)
            groups.append({"date": key, "items": items})
        return groups

    @staticmethod
    def _event_to_summary(event: dict[str, Any]) -> str:
        app = APP_NAMES.get(str(event.get("app_context") or ""), str(event.get("app_context") or "未知应用"))
        action = ACTION_NAMES.get(str(event.get("action") or ""), str(event.get("action") or "执行操作"))
        correction = CORRECTION_NAMES.get(
            str(event.get("correction_type") or ""),
            str(event.get("correction_type") or "进行了纠正"),
        )
        return f"在{app}场景下，Agent尝试{action}，你{correction}"

    @staticmethod
    def _date_key(ts: int) -> str:
        dt = datetime.fromtimestamp(int(ts))
        return f"{dt.year}年{dt.month}月{dt.day}日"
