# Operator Guide

This is the shortest practical CLI loop for the current Unit 1 tutor runtime.

## 1. Open or Resume a Session

```bash
python app/cli.py start-learning-session --learner app/domain/evidence/learner-record-with-summary.example.json
```

Read the returned `sessionStartGuide`.

- `openingLine`: how to start the turn
- `firstTutorQuestion`: the first question to ask
- `smallHint`: the next small nudge if the learner stalls
- `goodStoppingPoint`: what counts as enough progress for the step
- `watchFor`: common failure patterns to listen for

If the learner already has a resumable session, this command reuses it.
If not, it plans a new session from the latest recommendations and stores it as `activeSession`.

## 2. Record One Learner Turn

```bash
python app/cli.py run-learning-turn --learner app/domain/evidence/learner-record-with-live-session.example.json --input app/domain/evidence/observation-form-step-u1-s2.example.json
```

Read the returned `turnSummary`.

- `decision`: how the evaluator judged the submitted observation
- `sessionStatus`: whether the session is still `in_progress` or now `completed`
- `nextAction`: what the operator should do next

## 3. Follow the Next Action

If `nextAction` is `continue_active_session`:

- stay in the same session
- use `nextStepGuide`
- ask the next `firstTutorQuestion`

If `nextAction` is `review_next_recommendation`:

- the previous session is complete
- review `nextRecommendedSession`
- start a new session when ready

## 4. Write Back to File When Needed

To persist the updated learner record:

```bash
python app/cli.py start-learning-session --learner <learner-record.json> --write
python app/cli.py run-learning-turn --learner <learner-record.json> --input <observation-form.json> --write
```

## Guardrails

- The runtime remains conservative. `completed` means a step rubric was satisfied, not that mastery is officially approved.
- Recommendations and summaries remain provisional until thresholds and pass labels are approved in `docs/`.
- If a learner response feels mathematically ambiguous, prefer a cautious observation form over forcing auto-completion.
