"""Optional on-device semantic retrieval over privacy rules.

The encoder must already exist on disk. No remote model download is attempted.
Metadata scope remains a hard gate before semantic ranking.
"""

from __future__ import annotations

from pathlib import Path

from .evidence import Evidence, evidence_to_query
from .retriever import RuleRetriever
from .schema import PrivacyRule, RetrievalResult


class SemanticRuleRetriever(RuleRetriever):
    def __init__(self, model_path: str | Path, rules: list[PrivacyRule] | None = None):
        source = Path(model_path)
        if not source.is_dir():
            raise FileNotFoundError(f"Local embedding model not found: {source}")
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install torch and transformers for semantic retrieval") from exc
        super().__init__(rules=rules)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(str(source), local_files_only=True)
        self.model = AutoModel.from_pretrained(str(source), local_files_only=True).eval()
        self.documents = [self._document(rule) for rule in self.rules]
        self.embeddings = self._encode(self.documents)

    def _encode(self, texts: list[str]):
        import numpy as np

        result = []
        with self.torch.no_grad():
            for start in range(0, len(texts), 16):
                batch = self.tokenizer(texts[start:start + 16], padding=True,
                                       truncation=True, max_length=512, return_tensors="pt")
                vector = self.model(**batch).last_hidden_state[:, 0]
                vector = self.torch.nn.functional.normalize(vector, p=2, dim=1)
                result.extend(vector.cpu().numpy())
        return np.asarray(result)

    @staticmethod
    def _document(rule: PrivacyRule) -> str:
        return " ".join([rule.name, rule.description, *rule.pii_types, *rule.apps,
                         *rule.task_intents, *rule.context_terms, *rule.recipients,
                         *rule.sensitivities])

    def retrieve(self, evidence: Evidence, top_k: int = 8, min_score: float = 0.20) -> list[RetrievalResult]:
        import numpy as np

        query = evidence_to_query(evidence)
        query_vector = self._encode([query])[0]
        ranked = []
        for rule, vector in zip(self.rules, self.embeddings):
            if not rule.enabled or not self._eligible(rule, evidence):
                continue
            metadata_score, fields = self._score(rule, evidence, query)
            semantic_score = max(0.0, float(np.dot(query_vector, vector)))
            score = 0.65 * metadata_score + 0.35 * semantic_score
            if score >= min_score:
                ranked.append(RetrievalResult(rule, score, [*fields, "semantic"]))
        ranked.sort(key=lambda item: (-item.score, -item.rule.priority, item.rule.rule_id))
        return ranked[:max(1, top_k)]
