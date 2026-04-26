from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any

from guard_core import decide_from_rule_candidates, normalize_guard_event
from proxy_agent import TEMP_DIR, TempFileManager, get_privacy_agent, safe_suffix
from skill_registry.skill_db import SkillDB


PROJECT_ROOT = Path(__file__).resolve().parent
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"
MEMORY_LOG_ROOT = PROJECT_ROOT / "memory" / "logs"


class GuardBackendService:
    def __init__(self, db: SkillDB | None = None) -> None:
        self.db = db or SkillDB(db_path=str(SKILL_DB_PATH))
        self.agent = get_privacy_agent()

    def decide(self, event: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_guard_event(event)
        candidates = self._load_active_rule_candidates(normalized["user_id"])
        payload = decide_from_rule_candidates(normalized, candidates, retrieval_source="local_active_rules")
        self._write_guard_audit(
            normalized["user_id"],
            action="guard_decide",
            payload={
                "event": normalized,
                "judgment": payload["judgment"],
                "matched_rules": payload["matched_rules"],
                "needs_review": payload["needs_review"],
            },
        )
        return payload

    def analyze_image_bytes(
        self,
        image_bytes: bytes,
        filename: str,
        *,
        user_id: str,
        command: str,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        tfm = TempFileManager()
        try:
            input_path = tfm.write_bytes(image_bytes, safe_suffix(filename, default=".png"))
            ocr_texts = self._safe_ocr_texts(str(input_path))
            ocr_text = "\n".join(ocr_texts)

            scene_summary = self._safe_scene_summary(str(input_path), command)
            scene_source = "model_scene_summary" if scene_summary else "fallback_ocr_only"
            if not scene_summary:
                scene_summary = self._fallback_scene_summary(ocr_texts, command)

            retrieved_rules = self._safe_retrieval(str(input_path), command, user_id)
            analysis = self._safe_privacy_analysis(str(input_path), command)
            sensitive_texts = self._extract_sensitive_texts(analysis, ocr_texts)
            candidate_regions = self._detect_regions(str(input_path), sensitive_texts)

            normalized_event = self._build_event_from_analysis(
                user_id=user_id,
                command=command,
                ocr_text=ocr_text,
                analysis=analysis,
                scene_summary=scene_summary,
                sensitive_texts=sensitive_texts,
            )
            decision = self.decide(normalized_event)

            payload = {
                "success": True,
                "user_id": user_id,
                "command": command,
                "input_filename": filename,
                "ocr_text": ocr_text,
                "ocr_texts": ocr_texts,
                "scene_summary": scene_summary,
                "scene_summary_source": scene_source,
                "retrieved_rules": retrieved_rules,
                "normalized_event": normalized_event,
                "decision": decision,
                "candidate_keywords": sensitive_texts,
                "candidate_regions": candidate_regions,
                "components": {
                    "ocr": "RapidOCR",
                    "masker": "VisualMasker",
                    "scene_model": "MiniCPM/Ollama fallback",
                },
                "processing_time_ms": int((time.perf_counter() - started) * 1000),
            }
            self._write_guard_audit(
                user_id,
                action="guard_analyze",
                payload={
                    "command": command,
                    "matched_rules": decision["matched_rules"],
                    "candidate_keywords": sensitive_texts,
                    "scene_summary_source": scene_source,
                },
            )
            return payload
        finally:
            tfm.cleanup()

    def redact_image_bytes(
        self,
        image_bytes: bytes,
        filename: str,
        *,
        user_id: str,
        command: str,
        method: str = "blur",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        tfm = TempFileManager()
        try:
            input_path = tfm.write_bytes(image_bytes, safe_suffix(filename, default=".png"))
            analysis = self.analyze_image_bytes(
                image_bytes,
                filename,
                user_id=user_id,
                command=command,
            )
            sensitive_texts = list(analysis.get("candidate_keywords") or [])
            output_path = str(TEMP_DIR / f"masked_{Path(filename).stem}{safe_suffix(filename, default='.png')}")

            if sensitive_texts:
                mask_result = self.agent.smart_masker.mask(
                    str(input_path),
                    sensitive_texts=sensitive_texts,
                    output_path=output_path,
                    method=method,
                    return_regions=True,
                )
            else:
                Path(output_path).write_bytes(image_bytes)
                mask_result = {
                    "success": True,
                    "output_path": output_path,
                    "masked_count": 0,
                    "regions": [],
                }

            if not mask_result.get("success"):
                raise RuntimeError(str(mask_result.get("error") or "Masking failed."))

            output_bytes = Path(mask_result["output_path"]).read_bytes()
            mime_type, _ = mimetypes.guess_type(mask_result["output_path"])
            payload = {
                "success": True,
                "user_id": user_id,
                "command": command,
                "method": method,
                "output_filename": Path(mask_result["output_path"]).name,
                "mime_type": mime_type or "image/png",
                "image_base64": base64.b64encode(output_bytes).decode("ascii"),
                "detected_regions": mask_result.get("regions") or [],
                "masked_count": int(mask_result.get("masked_count") or 0),
                "processing_time_ms": int((time.perf_counter() - started) * 1000),
                "decision": analysis["decision"],
                "retrieved_rules": analysis["retrieved_rules"],
                "scene_summary": analysis["scene_summary"],
                "scene_summary_source": analysis["scene_summary_source"],
                "candidate_keywords": sensitive_texts,
            }
            self._write_guard_audit(
                user_id,
                action="guard_redact",
                payload={
                    "command": command,
                    "method": method,
                    "masked_count": payload["masked_count"],
                    "matched_rules": payload["decision"]["matched_rules"],
                },
            )
            return payload
        finally:
            tfm.cleanup()

    def _load_active_rule_candidates(self, user_id: str) -> list[dict[str, Any]]:
        rows, _ = self.db.list_skill_versions(
            user_id=user_id,
            lifecycle_status="active",
            page=1,
            page_size=1000,
        )
        return rows

    def _safe_ocr_texts(self, image_path: str) -> list[str]:
        try:
            return self.agent._get_ocr_texts(image_path)
        except Exception:
            return []

    def _safe_scene_summary(self, image_path: str, command: str) -> str:
        try:
            return str(self.agent._analyze_scene_description(image_path, command) or "").strip()
        except Exception:
            return ""

    def _safe_retrieval(self, image_path: str, command: str, user_id: str) -> list[dict[str, Any]]:
        try:
            rag_hits = self.agent._selfrag_retrieve(image_path, command) or []
            if rag_hits:
                return [
                    {
                        "source": "rag",
                        "document": str(hit.get("document") or ""),
                    }
                    for hit in rag_hits
                ]
        except Exception:
            pass

        fallback_hits = self.db.search_skills(
            user_id=user_id,
            task_goal=command,
            app_context="",
            action_keywords="",
            limit=5,
        )
        return [
            {
                "source": "active_skill_search",
                "skill_name": str(hit.get("skill_name") or ""),
                "version": str(hit.get("version") or ""),
                "scene": str(hit.get("scene") or ""),
                "rule_text": str(hit.get("rule_text") or ""),
            }
            for hit in fallback_hits
        ]

    def _safe_privacy_analysis(self, image_path: str, command: str) -> dict[str, Any]:
        try:
            result = self.agent.minicpm_client.analyze_privacy(
                image_path=image_path,
                user_command=command,
                prompt_loader=self.agent.prompt_loader,
            )
        except Exception as exc:
            return {"fallback_error": str(exc)}

        if not result.get("success"):
            return {"fallback_error": str(result.get("error") or "privacy_analysis_failed")}

        analysis = result.get("analysis")
        return analysis if isinstance(analysis, dict) else {"raw_response": analysis}

    def _extract_sensitive_texts(self, analysis: dict[str, Any], ocr_texts: list[str]) -> list[str]:
        sensitive_texts: list[str] = []
        mask_plan = analysis.get("mask_plan")
        if isinstance(mask_plan, list):
            for item in mask_plan:
                if isinstance(item, dict) and str(item.get("action") or "MASK").upper() == "MASK":
                    text = str(item.get("text") or "").strip()
                    if text:
                        sensitive_texts.append(text)

        if not sensitive_texts:
            fallback_infos = analysis.get("sensitive_info")
            if isinstance(fallback_infos, list):
                for item in fallback_infos:
                    if isinstance(item, dict):
                        text = str(item.get("text") or "").strip()
                        if text:
                            sensitive_texts.append(text)

        if not sensitive_texts and ocr_texts:
            sensitive_texts.extend(
                text for text in ocr_texts if any(char.isdigit() for char in text) and len(text.strip()) >= 6
            )

        unique: list[str] = []
        seen: set[str] = set()
        for text in sensitive_texts:
            normalized = text.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique[:20]

    def _detect_regions(self, image_path: str, sensitive_texts: list[str]) -> list[dict[str, Any]]:
        if not sensitive_texts:
            return []
        result = self.agent.smart_masker.detect(image_path, sensitive_texts)
        if not result.get("success"):
            return []
        return list(result.get("regions") or [])

    def _build_event_from_analysis(
        self,
        *,
        user_id: str,
        command: str,
        ocr_text: str,
        analysis: dict[str, Any],
        scene_summary: str,
        sensitive_texts: list[str],
    ) -> dict[str, Any]:
        pii_types = []
        mask_plan = analysis.get("mask_plan")
        if isinstance(mask_plan, list):
            for item in mask_plan:
                if isinstance(item, dict):
                    pii_type = str(item.get("pii_type") or "").strip()
                    if pii_type:
                        pii_types.append(pii_type)

        app_context = str(
            analysis.get("app_context")
            or analysis.get("page_context")
            or analysis.get("scene")
            or self._guess_app_context(scene_summary, ocr_text)
        ).strip()
        field = "、".join(pii_types) if pii_types else "、".join(sensitive_texts[:3])
        return {
            "user_id": user_id,
            "app_context": app_context,
            "intent": command,
            "action": command,
            "field": field,
            "content": ocr_text or scene_summary,
            "command": command,
        }

    @staticmethod
    def _fallback_scene_summary(ocr_texts: list[str], command: str) -> str:
        if ocr_texts:
            preview = " ".join(text.strip() for text in ocr_texts[:6] if str(text).strip())
            if preview:
                return f"OCR-only fallback for command '{command}': {preview[:120]}"
        return f"OCR-only fallback for command '{command}'."

    @staticmethod
    def _guess_app_context(scene_summary: str, ocr_text: str) -> str:
        haystack = f"{scene_summary} {ocr_text}".lower()
        for keyword in ("wechat", "微信", "alipay", "支付宝", "dingtalk", "钉钉", "xiaohongshu", "小红书", "taobao", "淘宝"):
            if keyword in haystack:
                return keyword
        return "unknown"

    def _write_guard_audit(self, user_id: str, *, action: str, payload: dict[str, Any]) -> None:
        try:
            target_dir = MEMORY_LOG_ROOT / user_id
            target_dir.mkdir(parents=True, exist_ok=True)
            audit_path = target_dir / "behavior_log.jsonl"
            line = {
                "ts": int(time.time()),
                "source": "guard_api",
                "action": action,
                **payload,
            }
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass
