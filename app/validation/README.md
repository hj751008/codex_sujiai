# Validation Guardrails

The repository does not yet define automated release gates or approved mastery
thresholds. This folder is reserved for lightweight checks that protect against
silent rule drift.

## Minimum Guardrails

- Reject data that replaces `UNDECIDED` rules with hidden defaults.
- Preserve `approvalStatus` or equivalent fields for provisional links.
- Require a `sourceDocs` reference for mastery, prerequisite, and recommendation content.
- Prefer "needs review" outputs when evidence is incomplete.

## Current Limitation

These checks are documentation-oriented guardrails, not proof that a learner
model has been fully validated.
