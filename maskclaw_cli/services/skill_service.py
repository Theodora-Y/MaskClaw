from __future__ import annotations

import difflib
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maskclaw_cli.context import PROJECT_ROOT, ConfigStore
from maskclaw_cli.output import truncate
from skill_registry.skill_db import SkillDB


USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"


@dataclass
class SkillRecord:
    user_id: str
    skill_name: str
    version: str
    path: Path
    skill_md_path: Path
    rules_json_path: Path | None
    metadata: dict[str, Any]
    rules: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        scene = self.rules.get("scene") or self.metadata.get("description") or self.skill_name
        app = self.rules.get("app_context_hint") or self.rules.get("app_context") or ""
        return {
            "skill": self.skill_name,
            "version": self.version,
            "status": self.rules.get("status") or self.metadata.get("status") or "active",
            "bucket": self.metadata.get("storage_bucket") or "",
            "app": app,
            "strategy": self.rules.get("strategy") or "",
            "confidence": self.rules.get("confidence") or self.metadata.get("confidence") or "",
            "scene": truncate(scene, 48),
            "path": str(self.path),
        }


@dataclass
class SkillSnapshot:
    user_id: str
    skill_name: str
    version: str
    source: str
    path: str | None
    skill_md: str
    rules: dict[str, Any]
    rules_text: str
    metadata: dict[str, Any]
    status: str

    def summary(self) -> dict[str, Any]:
        return {
            "skill": self.skill_name,
            "version": self.version,
            "source": self.source,
            "status": self.status,
            "path": self.path or "",
        }


class SkillService:
    def __init__(self, store: ConfigStore | None = None, db: SkillDB | None = None) -> None:
        self.store = store or ConfigStore()
        self.db = db or SkillDB(db_path=str(SKILL_DB_PATH))

    def resolve_user(self, user_id: str | None = None) -> str:
        if user_id:
            return user_id
        config = self.store.load()
        if config.current_user_id:
            return config.current_user_id
        raise ValueError("No user selected. Run `maskclaw auth login` or pass `--user <user_id>`.")

    def list_skills(
        self,
        user_id: str | None = None,
        status: str | None = None,
        app: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[SkillRecord]:
        uid = self.resolve_user(user_id)
        rows, total = self.db.list_skill_versions(
            uid,
            lifecycle_status=status,
            app=app,
            query=query,
            page=page,
            page_size=page_size,
        )
        return [self._record_from_db_row(uid, row) for row in rows]

    def list_skills_page(
        self,
        user_id: str | None = None,
        status: str | None = None,
        app: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        uid = self.resolve_user(user_id)
        rows, total = self.db.list_skill_versions(
            uid,
            lifecycle_status=status,
            app=app,
            query=query,
            page=page,
            page_size=page_size,
        )
        records = [self._record_from_db_row(uid, row) for row in rows]
        return {
            "user_id": uid,
            "skills": [record.summary() for record in records],
            "count": len(records),
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def get_skill(
        self,
        skill_name: str,
        version: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
    ) -> SkillRecord:
        uid = self.resolve_user(user_id)
        if version:
            detail = self.db.get_skill_detail(uid, skill_name, version)
            if not detail:
                raise ValueError(f"Skill not found: {skill_name} version {version}")
            record = self._record_from_db_row(uid, detail)
            if status and status != "all" and record.summary()["status"] != status:
                raise ValueError(f"Skill not found: {skill_name} version {version} with status {status}")
            return record

        history = [
            self._record_from_db_row(uid, row)
            for row in self.db.get_skill_history(uid, skill_name)
            if not status or status == "all" or str(row.get("status") or "active") == status
        ]
        if not history:
            raise ValueError(f"Skill not found: {skill_name}")
        if len(history) > 1:
            versions = ", ".join(sorted(record.version for record in history))
            raise ValueError(f"Multiple versions found for {skill_name}: {versions}. Pass --version.")
        return history[0]

    def show_skill(self, skill_name: str, version: str | None = None, user_id: str | None = None) -> dict[str, Any]:
        uid = self.resolve_user(user_id)
        record = self.get_skill(skill_name, version, uid)
        detail = self.db.get_skill_detail(uid, record.skill_name, record.version)
        if not detail:
            raise ValueError(f"Skill not found: {skill_name} version {version or record.version}")

        rules = self._normalize_rules_object(detail.get("rules_json_content"))
        skill_md = str(detail.get("skill_md_content") or "")
        rules_text = self._normalize_rules_text(
            rules,
            detail.get("rules_json_content") if isinstance(detail.get("rules_json_content"), str) else None,
        )
        return {
            "summary": {
                **record.summary(),
                "source": str(detail.get("source_table") or "skills"),
                "storage_bucket": str(detail.get("storage_bucket") or ""),
            },
            "metadata": self._parse_frontmatter_text(skill_md),
            "rules": rules,
            "skill_md": skill_md,
            "rules_json": rules_text,
        }

    def diff_skill(
        self,
        skill_name: str,
        version: str,
        against: str,
        user_id: str | None = None,
        context_lines: int = 3,
    ) -> dict[str, Any]:
        uid = self.resolve_user(user_id)
        current = self._resolve_snapshot(skill_name, version, uid, source="local")
        if against.lower() in {"registry", "db", "stored"}:
            baseline = self._resolve_snapshot(skill_name, version, uid, source="registry")
        else:
            baseline = self._resolve_snapshot(skill_name, against, uid, source="auto")

        skill_md_diff = self._make_diff(
            baseline.skill_md,
            current.skill_md,
            f"{baseline.source}:{baseline.skill_name}@{baseline.version}:SKILL.md",
            f"{current.source}:{current.skill_name}@{current.version}:SKILL.md",
            context_lines,
        )
        rules_diff = self._make_diff(
            baseline.rules_text,
            current.rules_text,
            f"{baseline.source}:{baseline.skill_name}@{baseline.version}:rules.json",
            f"{current.source}:{current.skill_name}@{current.version}:rules.json",
            context_lines,
        )
        rule_field_changes = self._diff_rule_fields(baseline.rules, current.rules)
        return {
            "user_id": uid,
            "skill_name": skill_name,
            "version": version,
            "comparison": {
                "current": current.summary(),
                "baseline": baseline.summary(),
                "against": against,
                "has_changes": bool(skill_md_diff or rules_diff or rule_field_changes),
            },
            "skill_md_diff": skill_md_diff,
            "rules_json_diff": rules_diff,
            "rule_field_changes": rule_field_changes,
        }

    def edit_skill(
        self,
        skill_name: str,
        version: str,
        user_id: str | None = None,
        editor: str | None = None,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        record = self.get_skill(skill_name, version, user_id)
        validation_before = self.validate_skill(skill_name, version, record.user_id)
        command: list[str] | None = None
        editor_name: str | None = None
        exit_code: int | None = None

        if not validate_only:
            command = self._build_editor_command(editor)
            editor_name = command[0]
            file_args, skipped_files, editor_note = self._select_editor_targets(command, record)
            completed = subprocess.run(
                command + file_args,
                cwd=str(record.path),
                check=False,
            )
            exit_code = completed.returncode
        else:
            file_args = []
            skipped_files = []
            editor_note = None

        validation_after = self.validate_skill(skill_name, version, record.user_id)
        if validate_only:
            db_sync: dict[str, Any] = {
                "applied": False,
                "status": "deferred",
                "note": "Validate-only mode does not rewrite skill_registry.db.",
            }
        elif validation_after["ok"]:
            sync_result = self.db.update_skill_contents_from_files(record.user_id, skill_name, version)
            if sync_result:
                db_sync = {
                    "applied": True,
                    "status": "synced",
                    "note": "Edited content has been synchronized to skill_registry.db.",
                    **sync_result,
                }
                self.db.add_notification(
                    user_id=record.user_id,
                    notif_type="skill_edited",
                    title="规则已更新",
                    body=f"已同步更新规则「{skill_name}」{version}",
                    skill_name=skill_name,
                    skill_version=version,
                    event_id=f"skill-edit-{record.user_id}-{skill_name}-{version}-{db_sync['updated_ts']}",
                    status="confirmed",
                )
            else:
                db_sync = {
                    "applied": False,
                    "status": "skipped",
                    "note": "Files were edited, but no on-disk snapshot could be synchronized back into the registry.",
                }
        else:
            db_sync = {
                "applied": False,
                "status": "blocked",
                "note": "Edited files failed validation, so the registry snapshot was not updated.",
            }

        return {
            "user_id": record.user_id,
            "skill_name": skill_name,
            "version": version,
            "editor": editor_name,
            "editor_command": command or [],
            "editor_opened": not validate_only,
            "editor_exit_code": exit_code,
            "editor_note": editor_note,
            "opened_files": file_args,
            "skipped_files": skipped_files,
            "files": {
                "skill_md": str(record.skill_md_path),
                "rules_json": str(record.rules_json_path) if record.rules_json_path else "",
                "directory": str(record.path),
            },
            "validation_before": validation_before,
            "validation_after": validation_after,
            "db_sync": db_sync,
        }

    def validate_skill(self, skill_name: str, version: str, user_id: str | None = None) -> dict[str, Any]:
        record = self.get_skill(skill_name, version, user_id)
        errors: list[str] = []
        warnings: list[str] = []

        if not record.skill_md_path.exists():
            errors.append("SKILL.md is missing.")
            skill_md_text = ""
        else:
            skill_md_text = record.skill_md_path.read_text(encoding="utf-8", errors="replace")
            if not skill_md_text.strip():
                errors.append("SKILL.md is empty.")

        metadata = self._parse_frontmatter_text(skill_md_text)
        if metadata:
            meta_name = str(metadata.get("name") or "").strip()
            meta_version = str(metadata.get("version") or "").strip()
            if meta_name and meta_name != record.skill_name:
                errors.append(f"Frontmatter name mismatch: expected {record.skill_name}, got {meta_name}.")
            if meta_version and meta_version != record.version:
                errors.append(f"Frontmatter version mismatch: expected {record.version}, got {meta_version}.")
        else:
            warnings.append("SKILL.md has no YAML frontmatter.")

        rules_text = ""
        rules_data: dict[str, Any] = {}
        if not record.rules_json_path or not record.rules_json_path.exists():
            errors.append("rules.json is missing.")
        else:
            rules_text = record.rules_json_path.read_text(encoding="utf-8", errors="replace")
            try:
                parsed = json.loads(rules_text)
            except json.JSONDecodeError as exc:
                errors.append(f"rules.json is invalid JSON: {exc.msg} at line {exc.lineno}.")
            else:
                if not isinstance(parsed, dict):
                    errors.append("rules.json must contain a JSON object.")
                else:
                    rules_data = parsed

        for field in ("scene", "strategy", "rule_text"):
            if not rules_data.get(field):
                warnings.append(f"rules.json is missing recommended field: {field}.")

        rules_version = str(rules_data.get("version") or "").strip()
        if rules_version and rules_version != record.version:
            warnings.append(f"rules.json version is {rules_version}, expected {record.version}.")

        rules_user = str(rules_data.get("user_id") or "").strip()
        if rules_user and rules_user != record.user_id:
            warnings.append(f"rules.json user_id is {rules_user}, expected {record.user_id}.")

        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "metadata": metadata,
            "rules": rules_data,
            "files": {
                "skill_md": str(record.skill_md_path),
                "rules_json": str(record.rules_json_path) if record.rules_json_path else "",
            },
        }

    def available_versions(self, skill_name: str, user_id: str | None = None) -> list[str]:
        uid = self.resolve_user(user_id)
        history = self.db.get_skill_history(uid, skill_name)
        versions = {str(row.get("version") or "") for row in history if row.get("version")}
        return sorted(v for v in versions if v)

    def archive_skill(
        self,
        skill_name: str,
        version: str,
        user_id: str | None = None,
        reason: str = "user_archived",
    ) -> dict[str, Any]:
        uid = self.resolve_user(user_id)
        ok = self.db.archive_skill(uid, skill_name, version, reason=reason)
        if not ok:
            raise ValueError(f"Archive failed for {skill_name} {version}. Check whether it is already archived.")

        ts = int(time.time())
        self.db.add_notification(
            user_id=uid,
            notif_type="skill_disabled",
            title="规则已停用",
            body=f"用户停用了规则「{skill_name}」{version}",
            skill_name=skill_name,
            skill_version=version,
            event_id=f"skill-archive-{uid}-{skill_name}-{version}-{ts}",
            status="confirmed",
        )
        detail = self.db.get_skill_detail(uid, skill_name, version)
        return {
            "ok": True,
            "user_id": uid,
            "skill_name": skill_name,
            "version": version,
            "status": detail.get("status") if detail else "archived",
            "storage_bucket": detail.get("storage_bucket") if detail else "trash",
        }

    def restore_skill(
        self,
        skill_name: str,
        version: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        uid = self.resolve_user(user_id)
        ok = self.db.restore_skill(uid, skill_name, version, str(USER_SKILLS_ROOT))
        if not ok:
            raise ValueError(f"Restore failed for {skill_name} {version}. Check whether it is archived and has valid content.")

        ts = int(time.time())
        self.db.add_notification(
            user_id=uid,
            notif_type="skill_enabled",
            title="规则已启用",
            body=f"用户启用了规则「{skill_name}」{version}",
            skill_name=skill_name,
            skill_version=version,
            event_id=f"skill-restore-{uid}-{skill_name}-{version}-{ts}",
            status="confirmed",
        )
        detail = self.db.get_skill_detail(uid, skill_name, version)
        return {
            "ok": True,
            "user_id": uid,
            "skill_name": skill_name,
            "version": version,
            "status": detail.get("status") if detail else "active",
            "storage_bucket": detail.get("storage_bucket") if detail else "active",
        }

    def _resolve_snapshot(
        self,
        skill_name: str,
        version: str,
        user_id: str,
        source: str = "auto",
    ) -> SkillSnapshot:
        if source in {"auto", "local"}:
            try:
                record = self.get_skill(skill_name, version, user_id)
            except ValueError:
                if source == "local":
                    raise
            else:
                if record.skill_md_path.exists():
                    skill_md = record.skill_md_path.read_text(encoding="utf-8", errors="replace")
                    rules_text = record.rules_json_path.read_text(encoding="utf-8", errors="replace") if record.rules_json_path and record.rules_json_path.exists() else ""
                    return SkillSnapshot(
                        user_id=record.user_id,
                        skill_name=record.skill_name,
                        version=record.version,
                        source="local",
                        path=str(record.path),
                        skill_md=skill_md,
                        rules=record.rules,
                        rules_text=self._normalize_rules_text(record.rules, rules_text),
                        metadata=record.metadata,
                        status=str(record.rules.get("status") or record.metadata.get("status") or "active"),
                    )

        detail = self.db.get_skill_detail(user_id, skill_name, version)
        if detail:
            rules = self._normalize_rules_object(detail.get("rules_json_content"))
            skill_md = str(detail.get("skill_md_content") or "")
            path = str(detail.get("path") or "") or None
            status = str(detail.get("status") or ("archived" if detail.get("archived_ts") else "stored"))
            return SkillSnapshot(
                user_id=user_id,
                skill_name=skill_name,
                version=version,
                source="registry",
                path=path,
                skill_md=skill_md,
                rules=rules,
                rules_text=self._normalize_rules_text(rules),
                metadata=self._parse_frontmatter_text(skill_md),
                status=status,
            )

        versions = self.available_versions(skill_name, user_id)
        hint = f" Available versions: {', '.join(versions)}." if versions else ""
        raise ValueError(f"Snapshot not found for {skill_name} {version}.{hint}")

    @staticmethod
    def _normalize_rules_object(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except Exception:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _normalize_rules_text(rules: dict[str, Any], fallback: str | None = None) -> str:
        if rules:
            return json.dumps(rules, ensure_ascii=False, indent=2, sort_keys=True)
        return fallback or ""

    @staticmethod
    def _make_diff(left: str, right: str, left_name: str, right_name: str, context_lines: int) -> list[str]:
        return list(
            difflib.unified_diff(
                left.splitlines(),
                right.splitlines(),
                fromfile=left_name,
                tofile=right_name,
                lineterm="",
                n=context_lines,
            )
        )

    @staticmethod
    def _diff_rule_fields(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            left_value = left.get(key)
            right_value = right.get(key)
            if left_value == right_value:
                continue
            changes.append({"field": key, "baseline": left_value, "current": right_value})
        return changes

    @staticmethod
    def _build_editor_command(editor: str | None = None) -> list[str]:
        raw = (editor or os.environ.get("VISUAL") or os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "vi")).strip()
        parts = shlex.split(raw, posix=os.name != "nt")
        if not parts:
            raise ValueError("No editor configured. Pass `--editor`, or set $EDITOR / $VISUAL.")
        executable = parts[0]
        resolved = shutil.which(executable)
        if resolved:
            parts[0] = resolved
        elif not Path(executable).exists():
            raise ValueError(f"Editor not found: {executable}")
        if Path(parts[0]).stem.lower() in {"code", "cursor", "codium"} and "-w" not in parts and "--wait" not in parts:
            parts.append("-w")
        return parts

    @staticmethod
    def _select_editor_targets(command: list[str], record: SkillRecord) -> tuple[list[str], list[str], str | None]:
        targets = [str(record.skill_md_path)]
        if record.rules_json_path:
            targets.append(str(record.rules_json_path))

        editor_stem = Path(command[0]).stem.lower()
        if editor_stem == "notepad":
            skipped = targets[1:]
            note = None
            if skipped:
                note = "Notepad is opened with SKILL.md only. Open rules.json separately if you need to edit both files."
            return targets[:1], skipped, note

        return targets, [], None

    @staticmethod
    def _read_rules(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _parse_frontmatter_text(text: str) -> dict[str, Any]:
        match = re.match(r"^---\s*\n(.*?)\n---\s*", text, flags=re.DOTALL)
        if not match:
            return {}
        metadata: dict[str, Any] = {}
        current_key: str | None = None
        for raw_line in match.group(1).splitlines():
            if not raw_line.strip():
                continue
            if raw_line.startswith(" ") and current_key:
                metadata[current_key] = f"{metadata.get(current_key, '')}\n{raw_line.strip()}".strip()
                continue
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            if value == ">":
                metadata[current_key] = ""
            else:
                metadata[current_key] = value.strip("\"'")
        return metadata

    def _record_from_db_row(self, user_id: str, row: dict[str, Any]) -> SkillRecord:
        skill_name = str(row.get("skill_name") or "")
        version = str(row.get("version") or "")
        status = str(row.get("status") or "active")
        raw_path = str(row.get("path") or "")
        if raw_path:
            skill_dir = Path(raw_path)
        else:
            base = USER_SKILLS_ROOT / user_id
            if status in {"pending", "draft", "rejected"}:
                base = USER_SKILLS_ROOT / ".review" / user_id
            elif status == "archived":
                base = USER_SKILLS_ROOT / ".trash" / user_id
            skill_dir = base / skill_name / version

        skill_md_text = str(row.get("skill_md_content") or "")
        metadata = self._parse_frontmatter_text(skill_md_text)
        metadata.setdefault("status", status)
        metadata.setdefault("confidence", row.get("confidence"))
        metadata.setdefault("storage_bucket", row.get("storage_bucket") or self._storage_bucket_name(status))
        rules = self._normalize_rules_object(row.get("rules_json_content"))
        rules.setdefault("status", status)
        return SkillRecord(
            user_id=user_id,
            skill_name=skill_name,
            version=version,
            path=skill_dir,
            skill_md_path=skill_dir / "SKILL.md",
            rules_json_path=skill_dir / "rules.json",
            metadata=metadata,
            rules=rules,
        )

    @staticmethod
    def _storage_bucket_name(status: str) -> str:
        if status in {"pending", "draft", "rejected"}:
            return "review"
        if status == "archived":
            return "trash"
        return "active"
