# Unit Pack Template

Use this template when preparing a future unit pack such as Unit 2.

This folder is intentionally not runtime-loaded. It exists to make new unit
packs consistent with the current Unit 1 structure without inventing curriculum
or mastery policy.

## Guardrails

- Do not fill any file from memory alone. Every content record should point to
  real source material in `docs/` or an explicitly provided reference.
- Do not invent new curriculum mappings, standard links, or textbook claims.
- Do not convert `UNDECIDED` thresholds into numeric cutoffs.
- Keep `status` values explicit, such as `draft-from-docs` or `provisional`.
- Keep `sourceDocs` on every reviewable content record.

## Expected file set

- `skills.template.json`
- `prerequisites.template.json`
- `recommendation-examples.template.json`
- `activity-recommendations.template.json`
- `lesson-steps.template.json`
- `evaluator-rubrics.template.json`
- `observation-form-mappings.template.json`
- `error-patterns.template.json`

## Suggested workflow

1. Copy this folder to `app/content/<unit-slug>/`.
2. Replace placeholder ids with the new unit's documented ids only.
3. Fill `sourceDocs` first, then content fields.
4. Run `python app/cli.py validate-content`.
5. Add or extend harness cases before trusting the new unit flow.
