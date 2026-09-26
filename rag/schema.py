"""Typed contracts for rule retrieval and policy decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


DECISIONS = {"ALLOW", "MASK", "ASK"}


@dataclass(frozen=True)
class PrivacyRule:
    """A policy rule stored in the local rule corpus.

    ``apps``, ``task_intents`` and ``recipients`` are metadata filters.  Empty
    lists mean the rule is generic rather than that the field is unknown.
    """

    rule_id: str
    name: str
    description: str
    action: str
    pii_types: List[str] = field(default_factory=list)
    apps: List[str] = field(default_factory=list)
    task_intents: List[str] = field(default_factory=list)
    context_terms: List[str] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    sensitivities: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    priority: int = 50
    enabled: bool = True
    source: str = "builtin"

    def __post_init__(self) -> None:
        action = self.action.upper()
        if action not in DECISIONS:
            raise ValueError(f"Unsupported rule action: {self.action}")
        object.__setattr__(self, "action", action)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrivacyRule":
        """Load both the new schema and the old strategy-based rule shape."""
        action = str(data.get("action") or "").upper()
        if not action:
            strategy = str(data.get("strategy") or "").lower()
            action = {"replace": "MASK", "block": "ASK", "allow": "ALLOW"}.get(strategy, "ASK")
        return cls(
            rule_id=str(data.get("rule_id") or data.get("id") or ""),
            name=str(data.get("name") or data.get("title") or data.get("rule_id") or "unnamed"),
            description=str(data.get("description") or data.get("rule_text") or data.get("document") or ""),
            action=action,
            pii_types=_as_list(data.get("pii_types") or data.get("sensitive_field")),
            apps=_as_list(data.get("apps") or data.get("app_context")),
            task_intents=_as_list(data.get("task_intents") or data.get("task")),
            context_terms=_as_list(data.get("context_terms")),
            recipients=_as_list(data.get("recipients") or data.get("recipient")),
            sensitivities=_as_list(data.get("sensitivities") or data.get("sensitivity")),
            exceptions=_as_list(data.get("exceptions")),
            priority=int(data.get("priority", 50)),
            enabled=bool(data.get("enabled", data.get("status", "active") == "active")),
            source=str(data.get("source") or "builtin"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "action": self.action,
            "pii_types": self.pii_types,
            "apps": self.apps,
            "task_intents": self.task_intents,
            "context_terms": self.context_terms,
            "recipients": self.recipients,
            "sensitivities": self.sensitivities,
            "exceptions": self.exceptions,
            "priority": self.priority,
            "enabled": self.enabled,
            "source": self.source,
        }


@dataclass(frozen=True)
class RetrievalResult:
    rule: PrivacyRule
    score: float
    matched_fields: List[str] = field(default_factory=list)
    distance: float | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule.to_dict(),
            "score": round(self.score, 4),
            "matched_fields": self.matched_fields,
            "distance": self.distance,
        }


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
