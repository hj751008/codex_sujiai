# Project Context

## Project Purpose
Build a Korean middle school math learning AI with strong math accuracy, honest validation, and curriculum-grounded behavior.

## Current Structure
- `app/`: application code
- `docs/`: project docs and session records
- `.agents/skills/`: repository-local agent workflows

## Source of Truth
- Repository docs in `docs/`
- Explicit curriculum/reference materials checked into the project
- Approved thresholds and rules documented in the repo

## Current App State
- `app/` now includes a schema-first Unit 1 runtime with content validation, learner summary, prerequisite-aware recommendations, session payload generation, session runner logic, and learner-record persistence
- The runtime is still intentionally conservative: mastery thresholds, pass labels, and scoring cutoffs remain provisional or undecided unless approved in `docs/`
- The current runnable flow reaches `learner_record -> activeSession -> observation submission -> learner summary/recommendation refresh`, but curriculum scope is still limited to Unit 1 prime factorization

## Next Priorities
1. Keep Unit 1 worked examples and app content evidence-backed and conservative
2. Expand failure-path validation for malformed learner/session state, not just happy-path harness cases
3. Grow beyond Unit 1 only after the existing conservative flow remains stable and reviewable
