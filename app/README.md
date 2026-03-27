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
- `content/templates/`: copy-safe scaffolds for future unit packs
- `validation/`: lightweight checks and guardrails for doc-backed logic

## Current Scope

The initial scaffold only models Unit 1 prime factorization because that is the
most concrete content currently documented in the repository.

## Operator Flow

For the current CLI-first tutoring loop, the smallest practical flow is:

1. `python app/cli.py start-learning-session --learner <learner-record.json>`
2. Show the returned `sessionStartGuide` to the tutor.
3. Run `python app/cli.py prepare-observation-form --learner <learner-record.json>` to get a strict observation draft from the current step and documented mappings only.
4. After the learner responds, run `python app/cli.py run-learning-turn --learner <learner-record.json> --input <observation-form.json>`.
5. Read `turnSummary.nextAction`.
6. If it says `continue_active_session`, stay in the current session and use `nextStepGuide`.
7. If it says `review_next_recommendation`, the previous session is complete and the next session should be chosen from the recommendation summary.

Some app-facing records may split broad documented skills into draft child
skills for diagnosis and recommendation. When that happens, keep the documented
parent skill explicit and mark the child records as draft or provisional rather
than treating them as approved curriculum policy.
