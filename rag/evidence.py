"""Structured evidence contract between local vision/OCR and the RAG layer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence


@dataclass(frozen=True)
class EvidenceRegion:
    """One OCR/vision region in source-image coordinates."""

    text: str = ""
    pii_type: str = "unknown"
    bbox: List[float] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "ocr"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceRegion":
        bbox = data.get("bbox") or data.get("box") or []
        return cls(
            text=str(data.get("text") or data.get("value") or ""),
            pii_type=str(data.get("pii_type") or data.get("type") or "unknown").lower(),
            bbox=[float(x) for x in bbox] if isinstance(bbox, (list, tuple)) else [],
            confidence=float(data.get("confidence", data.get("score", 0.0)) or 0.0),
            source=str(data.get("source") or "ocr"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "pii_type": self.pii_type,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(frozen=True)
class Evidence:
    """Privacy-relevant facts extracted on device.

    The free-form OCR text is intentionally not required.  Rule retrieval uses
    normalized labels and context; raw text and boxes stay local for masking.
    """

    app: str = "unknown"
    page: str = "unknown"
    task: str = "unknown"
    recipient: str = "unknown"
    recipient_trust: str = "unknown"
    pii_types: List[str] = field(default_factory=list)
    sensitivities: List[str] = field(default_factory=list)
    regions: List[EvidenceRegion] = field(default_factory=list)
    visual_summary: str = ""
    ocr_text: str = ""
    model_confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Evidence":
        region_values = data.get("regions") or data.get("sensitive_info") or data.get("mask_plan") or []
        regions = [EvidenceRegion.from_dict(item) for item in region_values if isinstance(item, Mapping)]
        pii_types = _as_list(data.get("pii_types")) or [r.pii_type for r in regions if r.pii_type != "unknown"]
        sensitivities = _as_list(data.get("sensitivities"))
        return cls(
            app=str(data.get("app") or data.get("app_context") or data.get("application") or "unknown").lower(),
            page=str(data.get("page") or data.get("screen") or data.get("scene") or "unknown").lower(),
            task=str(data.get("task") or data.get("task_intent") or data.get("user_task") or "unknown").lower(),
            recipient=str(data.get("recipient") or data.get("receiver") or "unknown").lower(),
            recipient_trust=str(data.get("recipient_trust") or data.get("trust") or "unknown").lower(),
            pii_types=[x.lower() for x in pii_types],
            sensitivities=[x.lower() for x in sensitivities],
            regions=regions,
            visual_summary=str(data.get("visual_summary") or data.get("scene_description") or ""),
            ocr_text=str(data.get("ocr_text") or ""),
            model_confidence=float(data.get("model_confidence", data.get("confidence", 0.0)) or 0.0),
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def from_json(cls, value: str) -> "Evidence":
        parsed = json.loads(value)
        if not isinstance(parsed, Mapping):
            raise ValueError("Evidence JSON must be an object")
        return cls.from_dict(parsed)

    def to_dict(self, include_raw_text: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "app": self.app,
            "page": self.page,
            "task": self.task,
            "recipient": self.recipient,
            "recipient_trust": self.recipient_trust,
            "pii_types": self.pii_types,
            "sensitivities": self.sensitivities,
            "regions": [r.to_dict() for r in self.regions],
            "visual_summary": self.visual_summary,
            "model_confidence": self.model_confidence,
            "metadata": self.metadata,
        }
        if include_raw_text:
            result["ocr_text"] = self.ocr_text
        return result


def evidence_from_dict(value: Mapping[str, Any]) -> Evidence:
    return Evidence.from_dict(value)


def evidence_to_query(evidence: Evidence) -> str:
    """Build a stable, privacy-minimized lexical query for retrieval."""
    parts = [evidence.app, evidence.page, evidence.task, evidence.recipient, evidence.recipient_trust]
    parts.extend(evidence.pii_types)
    parts.extend(evidence.sensitivities)
    if evidence.visual_summary:
        parts.append(evidence.visual_summary)
    return " ".join(part.strip() for part in parts if part and part != "unknown")


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
