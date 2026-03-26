# Recommendation MVP

The first recommendation layer is intentionally simple and conservative.

- Inputs: one evidence event plus documented Unit 1 content
- Primary mapping: error pattern -> skill -> recommendation example
- Output style: `practice` recommendations with `limited` confidence
- Safety rule: set `needsReview` to `true` until the repository approves stronger ranking logic
