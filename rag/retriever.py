"""Hybrid local rule retrieval.

Metadata overlap is weighted more heavily than text overlap.  An optional
Chroma index can be added later, but the deterministic fallback is always
available for tests and for devices without an embedding model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .evidence import Evidence, evidence_to_query
from .schema import PrivacyRule, RetrievalResult


DEFAULT_RULES_PATH = Path(__file__).with_name("default_rules.json")


class RuleRetriever:
    def __init__(self, rules: Iterable[PrivacyRule] | None = None, rules_path: str | Path | None = None):
        if rules is not None:
            self.rules = list(rules)
        else:
            self.rules = load_rules(rules_path or DEFAULT_RULES_PATH)

    def retrieve(self, evidence: Evidence, top_k: int = 8, min_score: float = 0.08) -> List[RetrievalResult]:
        query = evidence_to_query(evidence)
        ranked: List[RetrievalResult] = []
        for rule in self.rules:
            if not rule.enabled or not self._eligible(rule, evidence):
                continue
            score, fields = self._score(rule, evidence, query)
            if score >= min_score:
                ranked.append(RetrievalResult(rule=rule, score=score, matched_fields=fields))
        ranked.sort(key=lambda item: (-item.score, -item.rule.priority, item.rule.rule_id))
        return ranked[: max(1, top_k)]

    @staticmethod
    def _eligible(rule: PrivacyRule, evidence: Evidence) -> bool:
        """A lexical hit cannot override a conflicting policy scope."""
        def intersects(expected: Sequence[str], actual: Sequence[str]) -> bool:
            return bool({_normalize(x) for x in expected} & {_normalize(x) for x in actual})

        if rule.pii_types and evidence.pii_types and not intersects(rule.pii_types, evidence.pii_types):
            return False
        if rule.action == "ALLOW" and rule.apps and evidence.app == "unknown":
            return False
        if rule.action == "ALLOW" and rule.task_intents and evidence.task == "unknown":
            return False
        app_values = [evidence.app] if rule.action == "ALLOW" else [evidence.app, evidence.page]
        task_values = [evidence.task] if rule.action == "ALLOW" else [evidence.task, evidence.page]
        if rule.apps and evidence.app != "unknown" and not intersects(rule.apps, app_values):
            return False
        if rule.task_intents and evidence.task != "unknown" and not intersects(rule.task_intents, task_values):
            return False
        if rule.context_terms:
            context = _normalize(" ".join([evidence.app, evidence.page, evidence.task, evidence.recipient]))
            if not all(_normalize(term) in context for term in rule.context_terms):
                return False
        if rule.recipients and not intersects(rule.recipients, [evidence.recipient]):
            return False
        return True

    @staticmethod
    def _score(rule: PrivacyRule, evidence: Evidence, query: str) -> tuple[float, List[str]]:
        fields: List[str] = []
        score = 0.0

        def overlap(values: Sequence[str], observed: Sequence[str], weight: float, name: str) -> None:
            nonlocal score
            if not values:
                return
            values_norm = {_normalize(v) for v in values if _normalize(v)}
            observed_norm = {_normalize(v) for v in observed if _normalize(v)}
            if not observed_norm:
                return
            if values_norm & observed_norm:
                score += weight
                fields.append(name)
            elif name in {"app", "task", "recipient"}:
                # A specific rule should not be selected for a conflicting app
                # or recipient, even if its description happens to be similar.
                score -= weight * 0.45

        overlap(rule.pii_types, evidence.pii_types, 0.45, "pii_type")
        overlap(rule.sensitivities, evidence.sensitivities, 0.12, "sensitivity")
        overlap(rule.apps, [evidence.app, evidence.page], 0.16, "app")
        overlap(rule.task_intents, [evidence.task, evidence.page], 0.14, "task")
        if rule.context_terms:
            score += 0.12
            fields.append("context_terms")
        # Trust is a separate signal.  Do not let an unknown trust value make
        # a known recipient look like the literal recipient ``unknown``.
        overlap(rule.recipients, [evidence.recipient], 0.10, "recipient")

        text_tokens = _tokens(query)
        rule_tokens = _tokens(" ".join([rule.name, rule.description, *rule.pii_types, *rule.apps, *rule.task_intents]))
        if text_tokens and rule_tokens:
            lexical = len(text_tokens & rule_tokens) / max(1, len(text_tokens | rule_tokens))
            score += min(0.15, lexical * 0.3)
            if lexical >= 0.08:
                fields.append("lexical")
        return max(0.0, min(1.0, score)), fields


def load_rules(path: str | Path) -> List[PrivacyRule]:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    raw_rules = data.get("rules", data) if isinstance(data, (dict, list)) else []
    if not isinstance(raw_rules, list):
        raise ValueError(f"Rules file must contain a list or {{'rules': [...]}}: {source}")
    return [PrivacyRule.from_dict(item) for item in raw_rules if isinstance(item, Mapping)]


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-:/]+", "", str(value).lower())


def _tokens(value: str) -> set[str]:
    # Keep Chinese phrases intact while also retaining latin/numeric labels.
    return {token for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9]{2,}", value.lower()) if token}
