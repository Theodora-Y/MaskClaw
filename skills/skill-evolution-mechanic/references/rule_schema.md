# Rule Schema

Candidate rule object:

{
  "scene": "action:agent_fill_form",
  "sensitive_field": "unknown",
  "strategy": "avoid pattern triggering correction:user_modified_previous_action",
  "confidence": 0.8,
  "needs_review": false,
  "evidence_count": 3,
  "total_corrections": 5
}

Field notes:
- scene: compact scenario descriptor
- sensitive_field: target field or unknown
- strategy: natural-language policy
- confidence: float in [0, 1]
- needs_review: true when confidence < 0.7
- evidence_count: support count for this pattern
- total_corrections: total corrected samples considered
