from __future__ import annotations

import json
from typing import Any


ALLOWED_JUDGMENTS = {"allow", "block", "mask", "ask", "unsure"}


def normalize_guard_event(event: dict[str, Any], default_user_id: str | None = None) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("Guard event must be a JSON object.")

    user_id = str(event.get("user_id") or default_user_id or "").strip()
    if not user_id:
        raise ValueError("Guard event needs user_id, or configure a current user.")

    app_context = _norm(event.get("app_context") or event.get("app") or event.get("scene"))
    intent = _norm(event.get("intent") or event.get("task") or event.get("goal"))
    action = _norm(event.get("action") or intent)
    field = _norm(event.get("field") or event.get("sensitive_field") or event.get("pii_field"))
    content = _norm(event.get("content") or event.get("text") or event.get("ocr_text"))
    command = str(event.get("command") or event.get("user_command") or "").strip()

    return {
        "user_id": user_id,
        "app_context": app_context,
        "intent": intent,
        "action": action,
        "field": field,
        "content": content,
        "command": command,
    }


def decide_from_rule_candidates(
    event: dict[str, Any],
    rules: list[dict[str, Any]],
    *,
    retrieval_source: str = "local_active_rules",
) -> dict[str, Any]:
    normalized_event = normalize_guard_event(event)
    scored: list[dict[str, Any]] = []

    for raw_rule in rules:
        candidate = _build_candidate(raw_rule, normalized_event)
        if candidate is None:
            continue
        scored.append(candidate)

    scored.sort(key=lambda item: item["score"], reverse=True)
    retrieval_candidates = [
        {
            "rule_id": item["rule_id"],
            "skill_name": item["skill_name"],
            "version": item["version"],
            "score": round(float(item["score"]), 3),
            "strategy": item["strategy"],
            "scene": item["scene"],
            "rule_text": item["rule_text"],
        }
        for item in scored[:5]
    ]

    if not scored:
        return {
            "judgment": "unsure",
            "confidence": 0.0,
            "matched_rules": [],
            "reason": "No local rule matched this event.",
            "needs_review": True,
            "retrieval": {
                "source": retrieval_source,
                "count": 0,
                "candidates": [],
            },
            "decision_trace": {
                "normalized_event": normalized_event,
                "rules_considered": len(rules),
                "match_found": False,
            },
        }

    best = scored[0]
    judgment = best["strategy"] if best["strategy"] in ALLOWED_JUDGMENTS else "ask"
    confidence = max(_safe_float(best["confidence"], 0.0), float(best["score"]))

    return {
        "judgment": judgment,
        "confidence": round(min(confidence, 1.0), 3),
        "matched_rules": [best["rule_id"]],
        "reason": best["reason"] or "Matched a local active rule.",
        "needs_review": judgment in {"ask", "unsure"},
        "retrieval": {
            "source": retrieval_source,
            "count": len(retrieval_candidates),
            "candidates": retrieval_candidates,
        },
        "decision_trace": {
            "normalized_event": normalized_event,
            "rules_considered": len(rules),
            "match_found": True,
            "selected_rule": {
                "rule_id": best["rule_id"],
                "skill_name": best["skill_name"],
                "version": best["version"],
                "score": round(float(best["score"]), 3),
                "matched_features": best["matched_features"],
                "storage_bucket": best.get("storage_bucket", ""),
                "path": best.get("path", ""),
            },
            "top_candidates": retrieval_candidates[:3],
        },
    }


def _build_candidate(raw_rule: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    rules_payload = _normalize_rules_payload(raw_rule)
    if not rules_payload and not isinstance(raw_rule, dict):
        return None

    skill_name = str(raw_rule.get("skill_name") or rules_payload.get("skill_name") or "").strip()
    version = str(raw_rule.get("version") or rules_payload.get("version") or "").strip()
    path = str(raw_rule.get("path") or "").strip()
    storage_bucket = str(raw_rule.get("storage_bucket") or "").strip()

    rule_app = _norm(
        rules_payload.get("app_context_hint")
        or rules_payload.get("app_context")
        or raw_rule.get("scene")
        or rules_payload.get("scene")
    )
    rule_action = _norm(rules_payload.get("action") or raw_rule.get("strategy"))
    rule_field = _norm(rules_payload.get("field") or rules_payload.get("sensitive_field") or raw_rule.get("sensitive_field"))
    rule_scene = _norm(rules_payload.get("scene") or raw_rule.get("scene"))
    rule_text = str(rules_payload.get("rule_text") or raw_rule.get("rule_text") or "").strip()
    strategy = _norm(rules_payload.get("strategy") or raw_rule.get("strategy") or "ask")
    rule_id = str(
        rules_payload.get("rule_id")
        or rules_payload.get("id")
        or raw_rule.get("id")
        or f"{raw_rule.get('user_id', '')}:{skill_name}:{version}"
    ).strip()

    score = 0.0
    matched_features: list[str] = []
    if rule_app and event["app_context"] and (rule_app in event["app_context"] or event["app_context"] in rule_app):
        score += 0.45
        matched_features.append("app_context")
    if rule_action and event["action"] and (rule_action in event["action"] or event["action"] in rule_action):
        score += 0.25
        matched_features.append("action")
    if rule_field and event["field"] and (event["field"] in rule_field or rule_field in event["field"]):
        score += 0.2
        matched_features.append("field")
    if rule_field and event["content"] and any(part and part in event["content"] for part in _split_fields(rule_field)):
        score += 0.15
        matched_features.append("content")
    if rule_scene and event["content"] and rule_scene[:8] in event["content"]:
        score += 0.1
        matched_features.append("scene")
    if not matched_features and rule_text and event["content"] and any(
        token and token in event["content"] for token in _split_fields(rule_text)
    ):
        score += 0.1
        matched_features.append("rule_text")

    if score <= 0:
        return None

    return {
        "rule_id": rule_id,
        "skill_name": skill_name,
        "version": version,
        "path": path,
        "storage_bucket": storage_bucket,
        "strategy": strategy if strategy in ALLOWED_JUDGMENTS else "ask",
        "reason": rule_text or rules_payload.get("scene") or raw_rule.get("scene") or "",
        "confidence": rules_payload.get("confidence") or raw_rule.get("confidence") or score,
        "scene": str(rules_payload.get("scene") or raw_rule.get("scene") or ""),
        "rule_text": rule_text,
        "score": score,
        "matched_features": matched_features,
    }


def _normalize_rules_payload(raw_rule: dict[str, Any]) -> dict[str, Any]:
    rules_value = raw_rule.get("rules")
    if isinstance(rules_value, dict):
        return rules_value

    json_value = raw_rule.get("rules_json_content")
    if isinstance(json_value, dict):
        return json_value
    if isinstance(json_value, str) and json_value.strip():
        try:
            parsed = json.loads(json_value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    if isinstance(raw_rule, dict):
        return raw_rule
    return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _split_fields(value: str) -> list[str]:
    separators = ["、", ",", "，", "/", "|", "；", ";", " "]
    parts = [value]
    for separator in separators:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
    return [part.strip().lower() for part in parts if part.strip()]
