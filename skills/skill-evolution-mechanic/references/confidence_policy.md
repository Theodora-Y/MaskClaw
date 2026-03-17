# Confidence Policy

## Default policy
- Minimum support threshold: N >= 2
- Base confidence formula: confidence = min(0.95, 0.5 + 0.1 * N)
- Review gate: confidence < 0.7 -> needs_review = true

## Rationale
- Single correction is too noisy for policy generation.
- Rules below 0.7 confidence should not be auto-applied.

## Operational guidance
- If candidate_count is 0, keep existing rule base unchanged.
- If needs_review is true, require human confirmation before writing to RAG.
