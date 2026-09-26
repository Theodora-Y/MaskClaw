"""Auditable decision engine built on top of retrieval results."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List

from .evidence import Evidence
from .retriever import RuleRetriever
from .schema import DECISIONS, RetrievalResult


@dataclass(frozen=True)
class Decision:
    action: str
    confidence: float
    reason: str
    matched_rules: List[Dict[str, Any]] = field(default_factory=list)
    regions_to_mask: List[Dict[str, Any]] = field(default_factory=list)
    selected_rule_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "matched_rules": self.matched_rules,
            "regions_to_mask": self.regions_to_mask,
            "selected_rule_id": self.selected_rule_id,
        }


class DecisionEngine:
    """Retrieve candidate policies and resolve conflicts conservatively."""

    def __init__(self, retriever: RuleRetriever | None = None, min_match_score: float = 0.20):
        self.retriever = retriever or RuleRetriever()
        self.min_match_score = min_match_score

    def decide(self, evidence: Evidence, top_k: int = 8) -> Decision:
        candidates = self.retriever.retrieve(evidence, top_k=top_k, min_score=self.min_match_score)
        if not candidates:
            # Unknown sensitive material must not be silently forwarded.
            if evidence.pii_types or evidence.regions:
                return Decision("ASK", 0.35, "发现敏感证据但没有足够匹配的个性化规则", [], self._regions(evidence, mask=False))
            return Decision("ALLOW", 0.35, "没有检测到敏感证据，也没有匹配规则")

        # A narrowly matching explicit ALLOW can override a generic MASK rule,
        # but only with a meaningful score margin.  Otherwise restrictive
        # policies win, which prevents a broad semantic hit from leaking data.
        top = candidates[0]
        restrictive = [item for item in candidates if item.rule.action in {"MASK", "ASK"}]
        best_restrictive = max(restrictive, key=lambda item: (item.score, item.rule.priority)) if restrictive else None
        allow_covers_all = top.rule.action == "ALLOW" and self._allow_covers_evidence(top, evidence)
        if top.rule.action == "ALLOW" and (not allow_covers_all or (best_restrictive and top.score < best_restrictive.score + 0.10)):
            chosen = best_restrictive or top
            if not allow_covers_all and best_restrictive is None:
                return Decision("ASK", 0.4, "ALLOW 规则未覆盖所有检测到的敏感类型", [item.to_dict() for item in candidates], selected_rule_id=top.rule.rule_id)
        else:
            chosen = top
        action = chosen.rule.action if chosen.score >= self.min_match_score else "ASK"
        confidence = min(0.99, max(0.2, chosen.score + 0.2 * min(1.0, evidence.model_confidence)))
        matched = [item.to_dict() for item in candidates]
        region_output = self._regions(evidence, mask=action == "MASK")
        if action == "MASK" and len(set(evidence.pii_types)) > 1:
            # A rule for one field must not blur a different field that is
            # explicitly allowed in this same screenshot.
            region_output = [region.to_dict() for region in evidence.regions
                             if region.bbox and self.decide(replace(
                                 evidence, pii_types=[region.pii_type], regions=[]
                             ), top_k=top_k).action != "ALLOW"]
        reason = f"命中规则 {chosen.rule.rule_id}: {chosen.rule.description}"
        if action == "ASK":
            reason += "；需要用户确认后继续"
        return Decision(action, confidence, reason, matched, region_output, chosen.rule.rule_id)

    @staticmethod
    def _regions(evidence: Evidence, mask: bool) -> List[Dict[str, Any]]:
        if not mask:
            return []
        return [region.to_dict() for region in evidence.regions if region.bbox]

    @staticmethod
    def _allow_covers_evidence(candidate: RetrievalResult, evidence: Evidence) -> bool:
        """Do not let an ALLOW rule for one field release another field."""
        observed = {value.lower() for value in evidence.pii_types}
        covered = {value.lower() for value in candidate.rule.pii_types}
        if not observed or not covered:
            return True
        return observed.issubset(covered)
