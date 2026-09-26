"""Privacy-rule RAG package.

The package is deliberately independent from the screenshot proxy.  It accepts
structured evidence produced by local OCR/vision and returns an auditable
ALLOW/MASK/ASK decision.
"""

from .decision import DecisionEngine
from .evidence import Evidence, EvidenceRegion, evidence_from_dict, evidence_to_query
from .retriever import RuleRetriever
from .schema import PrivacyRule, RetrievalResult

__all__ = [
    "DecisionEngine",
    "Evidence",
    "EvidenceRegion",
    "PrivacyRule",
    "RetrievalResult",
    "RuleRetriever",
    "evidence_from_dict",
    "evidence_to_query",
]
