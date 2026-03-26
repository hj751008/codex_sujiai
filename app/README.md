# App Structure

This folder holds the first working app structure for `sujimathAI`.

The current repository docs intentionally leave mastery thresholds, scoring cutoffs,
and recommendation ranking rules as `UNDECIDED`. Because of that, this app
structure is schema-first and explanation-first rather than scoring-first.

## Design Rules

- Do not hard-code numeric mastery thresholds unless they are approved in `docs/`.
- Keep provisional and undecided states explicit in data.
- Prefer evidence records and explanation objects over opaque pass/fail flags.
- Treat curriculum, prerequisite, and recommendation logic as reviewable content.

## Layout

- `domain/`: shared data models and reviewable rule shapes
- `content/`: unit-specific skills, links, and recommendation examples
- `validation/`: lightweight checks and guardrails for doc-backed logic

## Current Scope

The initial scaffold only models Unit 1 prime factorization because that is the
most concrete content currently documented in the repository.

Some app-facing records may split broad documented skills into draft child
skills for diagnosis and recommendation. When that happens, keep the documented
parent skill explicit and mark the child records as draft or provisional rather
than treating them as approved curriculum policy.
