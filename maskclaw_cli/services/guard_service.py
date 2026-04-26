from __future__ import annotations

import base64
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from maskclaw_cli.context import ConfigStore
from maskclaw_cli.services.http_client import request_multipart_json
from maskclaw_cli.services.skill_service import SkillService
from guard_core import decide_from_rule_candidates, normalize_guard_event


class GuardService:
    def __init__(self, store: ConfigStore | None = None) -> None:
        self.store = store or ConfigStore()
        self.skills = SkillService(self.store)

    def load_event(self, input_path: str | None = None, use_stdin: bool = False) -> dict[str, Any]:
        if use_stdin:
            raw = sys.stdin.read()
        elif input_path:
            with open(input_path, "r", encoding="utf-8") as handle:
                raw = handle.read()
        else:
            raise ValueError("Pass --input <event.json> or --stdin.")
        data = json.loads(raw.lstrip("\ufeff"))
        if not isinstance(data, dict):
            raise ValueError("Guard event must be a JSON object.")
        return data

    def decide(self, event: dict[str, Any]) -> dict[str, Any]:
        config = self.store.load()
        normalized_event = normalize_guard_event(event, default_user_id=config.current_user_id)
        candidates = []
        for skill in self.skills.list_skills(normalized_event["user_id"], status="active", page_size=1000):
            candidates.append(
                {
                    "user_id": skill.user_id,
                    "skill_name": skill.skill_name,
                    "version": skill.version,
                    "path": str(skill.path),
                    "rules": skill.rules,
                }
            )
        return decide_from_rule_candidates(normalized_event, candidates, retrieval_source="local_active_rules")

    def analyze_image(self, image_path: str, command: str, user_id: str | None = None) -> dict[str, Any]:
        config = self.store.load()
        resolved_user_id = str(user_id or config.current_user_id or "").strip()
        if not resolved_user_id:
            raise ValueError("Pass --user or configure a current user before calling guard analyze.")

        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"Image not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(path.name)
        payload = request_multipart_json(
            "POST",
            f"{config.api_base_url}/guard/analyze",
            fields={"user_id": resolved_user_id, "command": command},
            files={"image": (path.name, path.read_bytes(), mime_type or "application/octet-stream")},
            token=config.token,
            timeout=60.0,
        )
        payload.setdefault("transport", "api")
        return payload

    def redact_image(
        self,
        image_path: str,
        command: str,
        output_path: str,
        *,
        method: str = "blur",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        config = self.store.load()
        resolved_user_id = str(user_id or config.current_user_id or "").strip()
        if not resolved_user_id:
            raise ValueError("Pass --user or configure a current user before calling guard redact.")

        source = Path(image_path)
        if not source.exists():
            raise ValueError(f"Image not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(source.name)
        payload = request_multipart_json(
            "POST",
            f"{config.api_base_url}/guard/redact",
            fields={"user_id": resolved_user_id, "command": command, "method": method},
            files={"image": (source.name, source.read_bytes(), mime_type or "application/octet-stream")},
            token=config.token,
            timeout=90.0,
        )
        image_base64 = str(payload.pop("image_base64", "") or "")
        if not image_base64:
            raise ValueError("Guard redact succeeded but no image payload was returned.")

        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(image_base64))
        payload["output_path"] = str(target)
        payload.setdefault("transport", "api")
        return payload

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _split_fields(value: str) -> list[str]:
        separators = ["、", ",", "，", "/", "|"]
        parts = [value]
        for sep in separators:
            next_parts: list[str] = []
            for part in parts:
                next_parts.extend(part.split(sep))
            parts = next_parts
        return [part.strip() for part in parts if part.strip()]
