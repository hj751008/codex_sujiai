from __future__ import annotations

import json
from pathlib import Path

from app.runtime.content_loader import load_unit1_content
from app.runtime.diagnostics import diagnose_event, summarize_learner, validate_evidence_event
from app.runtime.learner_record import (
    merge_session_into_learner_record,
    store_active_session,
    submit_observation_to_learner_record,
    validate_learner_record,
)
from app.runtime.session_orchestrator import resume_or_plan_session, start_learning_session
from app.runtime.session_planner import plan_next_session
from app.runtime.session_runner import (
    advance_session_state,
    apply_evaluator_decision,
    create_session_state,
    evaluate_current_step,
    observation_form_to_evaluation_input,
    session_history_to_evidence_events,
    submit_observation,
)


HARNESS_ROOT = Path(__file__).resolve().parent


def _load_cases() -> list[dict]:
    with (HARNESS_ROOT / "unit1_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_learner_summary_cases() -> list[dict]:
    with (HARNESS_ROOT / "learner_summary_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_session_runner_cases() -> list[dict]:
    with (HARNESS_ROOT / "session_runner_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_evaluator_cases() -> list[dict]:
    with (HARNESS_ROOT / "evaluator_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_observation_submission_cases() -> list[dict]:
    with (HARNESS_ROOT / "observation_submission_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_session_history_summary_cases() -> list[dict]:
    with (HARNESS_ROOT / "session_history_summary_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_learner_record_cases() -> list[dict]:
    with (HARNESS_ROOT / "learner_record_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_session_planner_cases() -> list[dict]:
    with (HARNESS_ROOT / "session_planner_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_session_orchestrator_cases() -> list[dict]:
    with (HARNESS_ROOT / "session_orchestrator_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_active_session_cases() -> list[dict]:
    with (HARNESS_ROOT / "active_session_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_learner_record_submission_cases() -> list[dict]:
    with (HARNESS_ROOT / "learner_record_submission_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_failure_cases() -> list[dict]:
    with (HARNESS_ROOT / "failure_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_start_learning_session_cases() -> list[dict]:
    with (HARNESS_ROOT / "start_learning_session_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _assert_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    event = case["event"]
    expected = case["expected"]

    validation_errors = validate_evidence_event(event)
    if validation_errors:
        return [f"{case['name']}: invalid evidence input: {'; '.join(validation_errors)}"]

    result = diagnose_event(content, event)
    recommendation_skill_ids = [record["targetSkillId"] for record in result.recommendations]
    activity_ids = [
        activity["activityId"]
        for record in result.recommendations
        for activity in record.get("recommendedActivities", [])
    ]
    lesson_step_ids = [
        step["lessonStepId"]
        for record in result.recommendations
        for step in record.get("sessionPayload", {}).get("steps", [])
    ]

    if result.mastery["skillId"] != expected["masterySkillId"]:
        failures.append(
            f"{case['name']}: expected mastery skill {expected['masterySkillId']}, got {result.mastery['skillId']}."
        )

    if result.mastery["status"] != expected["masteryStatus"]:
        failures.append(
            f"{case['name']}: expected mastery status {expected['masteryStatus']}, got {result.mastery['status']}."
        )

    if recommendation_skill_ids != expected["recommendationSkillIds"]:
        failures.append(
            f"{case['name']}: expected recommendations {expected['recommendationSkillIds']}, got {recommendation_skill_ids}."
        )
    if activity_ids != expected["activityIds"]:
        failures.append(
            f"{case['name']}: expected activity ids {expected['activityIds']}, got {activity_ids}."
        )
    if lesson_step_ids != expected["lessonStepIds"]:
        failures.append(
            f"{case['name']}: expected lesson step ids {expected['lessonStepIds']}, got {lesson_step_ids}."
        )

    return failures


def _assert_learner_summary_case(case: dict, content) -> list[str]:
    failures: list[str] = []

    try:
        result = summarize_learner(content, case["events"])
    except ValueError as exc:
        return [f"{case['name']}: learner summary failed unexpectedly: {exc}"]

    expected = case["expected"]
    actual_skill_ids = [record["skillId"] for record in result.skillSummaries]
    if actual_skill_ids != expected["skillIds"]:
        failures.append(
            f"{case['name']}: expected skill summaries {expected['skillIds']}, got {actual_skill_ids}."
        )

    for record in result.skillSummaries:
        expected_status = expected["statuses"].get(record["skillId"])
        if record["status"] != expected_status:
            failures.append(
                f"{case['name']}: expected {record['skillId']} status {expected_status}, got {record['status']}."
            )

    actual_required_blocked = [
        record["skillId"] for record in result.skillSummaries if record.get("hasRequiredPrerequisiteBlocker")
    ]
    if actual_required_blocked != expected["requiredBlockedSkills"]:
        failures.append(
            f"{case['name']}: expected required prerequisite blockers {expected['requiredBlockedSkills']}, got {actual_required_blocked}."
        )

    actual_helpful_blocked = [
        record["skillId"]
        for record in result.skillSummaries
        if record.get("blockedByPrerequisites") and not record.get("hasRequiredPrerequisiteBlocker")
    ]
    if actual_helpful_blocked != expected["helpfulBlockedSkills"]:
        failures.append(
            f"{case['name']}: expected helpful prerequisite blockers {expected['helpfulBlockedSkills']}, got {actual_helpful_blocked}."
        )

    actual_recommendation_skill_ids = [record["targetSkillId"] for record in result.recommendations]
    if actual_recommendation_skill_ids != expected["recommendationSkillIds"]:
        failures.append(
            f"{case['name']}: expected learner recommendations {expected['recommendationSkillIds']}, got {actual_recommendation_skill_ids}."
        )

    for record in result.recommendations:
        expected_next = expected["recommendedNextSkillIds"].get(record["targetSkillId"])
        actual_next = record.get("recommendedNextSkillIds")
        if actual_next != expected_next:
            failures.append(
                f"{case['name']}: expected next-skill chain {expected_next} for {record['targetSkillId']}, got {actual_next}."
            )
        expected_activity_sequence = expected["recommendedActivitySequenceIds"].get(record["targetSkillId"])
        actual_activity_sequence = [activity["activityId"] for activity in record.get("recommendedActivitySequence", [])]
        if actual_activity_sequence != expected_activity_sequence:
            failures.append(
                f"{case['name']}: expected activity sequence {expected_activity_sequence} for {record['targetSkillId']}, got {actual_activity_sequence}."
            )
        expected_session_steps = expected["sessionLessonStepIds"].get(record["targetSkillId"])
        actual_session_steps = [step["lessonStepId"] for step in record.get("sessionPayload", {}).get("steps", [])]
        if actual_session_steps != expected_session_steps:
            failures.append(
                f"{case['name']}: expected session lesson steps {expected_session_steps} for {record['targetSkillId']}, got {actual_session_steps}."
            )

    return failures


def _assert_session_runner_case(case: dict) -> list[str]:
    failures: list[str] = []
    recommendation_path = Path(HARNESS_ROOT.parent.parent, case["recommendationFile"])
    with recommendation_path.open("r", encoding="utf-8") as handle:
        recommendation = json.load(handle)

    state = create_session_state(recommendation)
    expected_start = case["expectedStart"]
    if state["status"] != expected_start["status"]:
        failures.append(f"{case['name']}: expected start status {expected_start['status']}, got {state['status']}.")
    if state["currentStep"]["lessonStepId"] != expected_start["currentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected current step {expected_start['currentLessonStepId']}, got {state['currentStep']['lessonStepId']}."
        )
    actual_next = state["nextStep"]["lessonStepId"] if state["nextStep"] else None
    if actual_next != expected_start["nextLessonStepId"]:
        failures.append(f"{case['name']}: expected next step {expected_start['nextLessonStepId']}, got {actual_next}.")
    if state["remainingStepIds"] != expected_start["remainingStepIds"]:
        failures.append(
            f"{case['name']}: expected remaining ids {expected_start['remainingStepIds']}, got {state['remainingStepIds']}."
        )

    for advance_case in case["advanceSequence"]:
        state = advance_session_state(state, advance_case["completeStep"])
        expected = advance_case["expected"]
        actual_current = state["currentStep"]["lessonStepId"] if state["currentStep"] else None
        actual_next = state["nextStep"]["lessonStepId"] if state["nextStep"] else None

        if state["status"] != expected["status"]:
            failures.append(f"{case['name']}: expected advanced status {expected['status']}, got {state['status']}.")
        if actual_current != expected["currentLessonStepId"]:
            failures.append(
                f"{case['name']}: expected current step {expected['currentLessonStepId']}, got {actual_current}."
            )
        if actual_next != expected["nextLessonStepId"]:
            failures.append(f"{case['name']}: expected next step {expected['nextLessonStepId']}, got {actual_next}.")
        if state["completedStepIds"] != expected["completedStepIds"]:
            failures.append(
                f"{case['name']}: expected completed steps {expected['completedStepIds']}, got {state['completedStepIds']}."
            )

    return failures


def _assert_evaluator_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    session_path = Path(HARNESS_ROOT.parent.parent, case["sessionFile"])
    with session_path.open("r", encoding="utf-8") as handle:
        session_state = json.load(handle)

    if "observationFormInput" in case:
        evaluation_input = observation_form_to_evaluation_input(
            session_state,
            case["observationFormInput"],
            content.observation_form_mappings,
        )
    else:
        evaluation_input = case["evaluationInput"]

    evaluation_result = evaluate_current_step(session_state, evaluation_input, content.evaluator_rubrics)
    expected_eval = case["expectedEvaluation"]
    if evaluation_result["lessonStepId"] != expected_eval["lessonStepId"]:
        failures.append(
            f"{case['name']}: expected lesson step {expected_eval['lessonStepId']}, got {evaluation_result['lessonStepId']}."
        )
    if evaluation_result["decision"] != expected_eval["decision"]:
        failures.append(
            f"{case['name']}: expected decision {expected_eval['decision']}, got {evaluation_result['decision']}."
        )
    if evaluation_result["canAutoAdvance"] != expected_eval["canAutoAdvance"]:
        failures.append(
            f"{case['name']}: expected canAutoAdvance {expected_eval['canAutoAdvance']}, got {evaluation_result['canAutoAdvance']}."
        )

    applied_state = apply_evaluator_decision(session_state, evaluation_result)
    expected_state = case["expectedAppliedState"]
    actual_current = applied_state["currentStep"]["lessonStepId"] if applied_state["currentStep"] else None
    if applied_state["status"] != expected_state["status"]:
        failures.append(f"{case['name']}: expected applied status {expected_state['status']}, got {applied_state['status']}.")
    if actual_current != expected_state["currentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected current step {expected_state['currentLessonStepId']}, got {actual_current}."
        )
    if applied_state["completedStepIds"] != expected_state["completedStepIds"]:
        failures.append(
            f"{case['name']}: expected completed ids {expected_state['completedStepIds']}, got {applied_state['completedStepIds']}."
        )

    return failures


def _assert_observation_submission_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    session_path = Path(HARNESS_ROOT.parent.parent, case["sessionFile"])
    with session_path.open("r", encoding="utf-8") as handle:
        session_state = json.load(handle)

    updated_state = submit_observation(
        session_state,
        case["observationFormInput"],
        content.evaluator_rubrics,
        content.observation_form_mappings,
    )
    expected = case["expected"]

    actual_current = updated_state["currentStep"]["lessonStepId"] if updated_state["currentStep"] else None
    if updated_state["status"] != expected["status"]:
        failures.append(f"{case['name']}: expected status {expected['status']}, got {updated_state['status']}.")
    if actual_current != expected["currentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected current step {expected['currentLessonStepId']}, got {actual_current}."
        )
    if updated_state["completedStepIds"] != expected["completedStepIds"]:
        failures.append(
            f"{case['name']}: expected completed ids {expected['completedStepIds']}, got {updated_state['completedStepIds']}."
        )
    if len(updated_state.get("history", [])) != expected["historyCount"]:
        failures.append(
            f"{case['name']}: expected history count {expected['historyCount']}, got {len(updated_state.get('history', []))}."
        )
    if updated_state.get("history"):
        record = updated_state["history"][0]
        if record["lessonStepId"] != expected["historyLessonStepId"]:
            failures.append(
                f"{case['name']}: expected history lesson step {expected['historyLessonStepId']}, got {record['lessonStepId']}."
            )
        if record["evaluation"]["decision"] != expected["historyDecision"]:
            failures.append(
                f"{case['name']}: expected history decision {expected['historyDecision']}, got {record['evaluation']['decision']}."
            )

    return failures


def _assert_session_history_summary_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    session_path = Path(HARNESS_ROOT.parent.parent, case["sessionFile"])
    with session_path.open("r", encoding="utf-8") as handle:
        session_state = json.load(handle)

    updated_state = submit_observation(
        session_state,
        case["observationFormInput"],
        content.evaluator_rubrics,
        content.observation_form_mappings,
    )
    events = session_history_to_evidence_events(updated_state)
    result = summarize_learner(content, events)
    expected = case["expected"]

    if len(events) != expected["eventCount"]:
        failures.append(f"{case['name']}: expected event count {expected['eventCount']}, got {len(events)}.")

    actual_event_skill_ids = [event["skillId"] for event in events]
    if actual_event_skill_ids != expected["eventSkillIds"]:
        failures.append(
            f"{case['name']}: expected event skill ids {expected['eventSkillIds']}, got {actual_event_skill_ids}."
        )

    actual_summary_skill_ids = [record["skillId"] for record in result.skillSummaries]
    if actual_summary_skill_ids != expected["summarySkillIds"]:
        failures.append(
            f"{case['name']}: expected summary skill ids {expected['summarySkillIds']}, got {actual_summary_skill_ids}."
        )

    for record in result.skillSummaries:
        expected_status = expected["summaryStatuses"].get(record["skillId"])
        if record["status"] != expected_status:
            failures.append(
                f"{case['name']}: expected {record['skillId']} status {expected_status}, got {record['status']}."
            )

    return failures


def _assert_learner_record_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    session_path = Path(HARNESS_ROOT.parent.parent, case["sessionFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)
    with session_path.open("r", encoding="utf-8") as handle:
        session_state = json.load(handle)

    updated_record = merge_session_into_learner_record(learner_record, session_state, content)
    expected = case["expected"]

    if len(updated_record.get("sessions", [])) != expected["sessionCount"]:
        failures.append(
            f"{case['name']}: expected session count {expected['sessionCount']}, got {len(updated_record.get('sessions', []))}."
        )
    if len(updated_record.get("evidenceEvents", [])) != expected["evidenceEventCount"]:
        failures.append(
            f"{case['name']}: expected evidence count {expected['evidenceEventCount']}, got {len(updated_record.get('evidenceEvents', []))}."
        )

    actual_skill_ids = [record["skillId"] for record in updated_record.get("latestSkillSummaries", [])]
    if actual_skill_ids != expected["latestSkillIds"]:
        failures.append(
            f"{case['name']}: expected latest skill ids {expected['latestSkillIds']}, got {actual_skill_ids}."
        )

    for record in updated_record.get("latestSkillSummaries", []):
        expected_status = expected["latestStatuses"].get(record["skillId"])
        if record["status"] != expected_status:
            failures.append(
                f"{case['name']}: expected latest status {expected_status} for {record['skillId']}, got {record['status']}."
            )

    actual_recommendation_skill_ids = [record["targetSkillId"] for record in updated_record.get("latestRecommendations", [])]
    if actual_recommendation_skill_ids != expected["recommendationSkillIds"]:
        failures.append(
            f"{case['name']}: expected recommendation skill ids {expected['recommendationSkillIds']}, got {actual_recommendation_skill_ids}."
        )

    return failures


def _assert_session_planner_case(case: dict) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)

    planned = plan_next_session(learner_record)
    expected = case["expected"]

    if planned["plannedFromSkillId"] != expected["plannedFromSkillId"]:
        failures.append(
            f"{case['name']}: expected planned skill {expected['plannedFromSkillId']}, got {planned['plannedFromSkillId']}."
        )
    if planned["recommendedNextSkillIds"] != expected["recommendedNextSkillIds"]:
        failures.append(
            f"{case['name']}: expected next skill ids {expected['recommendedNextSkillIds']}, got {planned['recommendedNextSkillIds']}."
        )
    if planned["sessionPreview"]["firstLessonStepId"] != expected["firstLessonStepId"]:
        failures.append(
            f"{case['name']}: expected first lesson step {expected['firstLessonStepId']}, got {planned['sessionPreview']['firstLessonStepId']}."
        )
    if planned["sessionPreview"]["stepCount"] != expected["stepCount"]:
        failures.append(
            f"{case['name']}: expected step count {expected['stepCount']}, got {planned['sessionPreview']['stepCount']}."
        )

    return failures


def _assert_session_orchestrator_case(case: dict) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)

    result = resume_or_plan_session(learner_record)
    expected = case["expected"]

    if result["action"] != expected["action"]:
        failures.append(f"{case['name']}: expected action {expected['action']}, got {result['action']}.")

    if result["action"] == "resume_session":
        preview = result.get("resumePreview", {})
        if preview.get("targetSkillId") != expected["targetSkillId"]:
            failures.append(
                f"{case['name']}: expected resume target skill {expected['targetSkillId']}, got {preview.get('targetSkillId')}."
            )
        if preview.get("currentLessonStepId") != expected["currentLessonStepId"]:
            failures.append(
                f"{case['name']}: expected current lesson step {expected['currentLessonStepId']}, got {preview.get('currentLessonStepId')}."
            )
        if preview.get("remainingStepCount") != expected["remainingStepCount"]:
            failures.append(
                f"{case['name']}: expected remaining step count {expected['remainingStepCount']}, got {preview.get('remainingStepCount')}."
            )
    else:
        planned = result.get("plannedSession", {})
        preview = planned.get("sessionPreview", {})
        if planned.get("plannedFromSkillId") != expected["plannedFromSkillId"]:
            failures.append(
                f"{case['name']}: expected planned skill {expected['plannedFromSkillId']}, got {planned.get('plannedFromSkillId')}."
            )
        if preview.get("firstLessonStepId") != expected["firstLessonStepId"]:
            failures.append(
                f"{case['name']}: expected first lesson step {expected['firstLessonStepId']}, got {preview.get('firstLessonStepId')}."
            )

    return failures


def _assert_active_session_case(case: dict) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)

    orchestration_result = resume_or_plan_session(learner_record)
    updated_record = store_active_session(learner_record, orchestration_result)
    expected = case["expected"]
    active_session = updated_record.get("activeSession")

    if active_session is None:
        return [f"{case['name']}: expected activeSession to be stored, but it was null."]

    if active_session.get("targetSkillId") != expected["targetSkillId"]:
        failures.append(
            f"{case['name']}: expected active session target skill {expected['targetSkillId']}, got {active_session.get('targetSkillId')}."
        )
    current_step = active_session.get("currentStep") or {}
    if current_step.get("lessonStepId") != expected["currentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected current lesson step {expected['currentLessonStepId']}, got {current_step.get('lessonStepId')}."
        )
    if active_session.get("status") != expected["status"]:
        failures.append(
            f"{case['name']}: expected active session status {expected['status']}, got {active_session.get('status')}."
        )

    return failures


def _assert_learner_record_submission_case(case: dict, content) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)

    updated_record = submit_observation_to_learner_record(learner_record, case["observationFormInput"], content)
    expected = case["expected"]
    active_session = updated_record.get("activeSession") or {}
    active_current = (active_session.get("currentStep") or {}).get("lessonStepId")

    if active_session.get("targetSkillId") != expected["activeTargetSkillId"]:
        failures.append(
            f"{case['name']}: expected active target skill {expected['activeTargetSkillId']}, got {active_session.get('targetSkillId')}."
        )
    if active_current != expected["activeCurrentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected active current step {expected['activeCurrentLessonStepId']}, got {active_current}."
        )
    if active_session.get("completedStepIds") != expected["activeCompletedStepIds"]:
        failures.append(
            f"{case['name']}: expected active completed ids {expected['activeCompletedStepIds']}, got {active_session.get('completedStepIds')}."
        )

    actual_recommendation_skill_ids = [record["targetSkillId"] for record in updated_record.get("latestRecommendations", [])]
    if actual_recommendation_skill_ids != expected["latestRecommendationSkillIds"]:
        failures.append(
            f"{case['name']}: expected latest recommendation ids {expected['latestRecommendationSkillIds']}, got {actual_recommendation_skill_ids}."
        )
    if len(updated_record.get("evidenceEvents", [])) != expected["evidenceEventCount"]:
        failures.append(
            f"{case['name']}: expected evidence event count {expected['evidenceEventCount']}, got {len(updated_record.get('evidenceEvents', []))}."
        )

    return failures


def _assert_failure_case(case: dict, content) -> list[str]:
    learner_record = None
    if "learnerFile" in case:
        learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
        with learner_path.open("r", encoding="utf-8") as handle:
            learner_record = json.load(handle)
    else:
        learner_record = case["learnerRecord"]

    try:
        if case["kind"].startswith("submit_observation_to_learner_record"):
            submit_observation_to_learner_record(learner_record, case["observationFormInput"], content)
        elif case["kind"] == "validate_learner_record":
            errors = validate_learner_record(learner_record)
            if not errors:
                return [f"{case['name']}: expected validation errors but validation passed."]
            combined = "; ".join(errors)
            if case["expectedErrorContains"] not in combined:
                return [
                    f"{case['name']}: expected validation error containing {case['expectedErrorContains']!r}, got {combined!r}."
                ]
            return []
        else:
            return [f"{case['name']}: unsupported failure case kind {case['kind']}."]
    except ValueError as exc:
        if case["expectedErrorContains"] not in str(exc):
            return [
                f"{case['name']}: expected error containing {case['expectedErrorContains']!r}, got {str(exc)!r}."
            ]
        return []

    return [f"{case['name']}: expected ValueError but the call succeeded."]


def _assert_start_learning_session_case(case: dict) -> list[str]:
    failures: list[str] = []
    learner_path = Path(HARNESS_ROOT.parent.parent, case["learnerFile"])
    with learner_path.open("r", encoding="utf-8") as handle:
        learner_record = json.load(handle)

    result = start_learning_session(learner_record)
    expected = case["expected"]
    guide = result.get("sessionStartGuide", {})
    active_session = result.get("activeSession", {})

    if result.get("action") != expected["action"]:
        failures.append(f"{case['name']}: expected action {expected['action']}, got {result.get('action')}.")
    if guide.get("targetSkillId") != expected["targetSkillId"]:
        failures.append(
            f"{case['name']}: expected target skill {expected['targetSkillId']}, got {guide.get('targetSkillId')}."
        )
    if guide.get("currentLessonStepId") != expected["currentLessonStepId"]:
        failures.append(
            f"{case['name']}: expected current step {expected['currentLessonStepId']}, got {guide.get('currentLessonStepId')}."
        )
    if guide.get("firstTutorQuestion") != expected["firstTutorQuestion"]:
        failures.append(
            f"{case['name']}: expected first tutor question {expected['firstTutorQuestion']!r}, got {guide.get('firstTutorQuestion')!r}."
        )
    if guide.get("nextLessonStepId") != expected["nextLessonStepId"]:
        failures.append(
            f"{case['name']}: expected next lesson step {expected['nextLessonStepId']}, got {guide.get('nextLessonStepId')}."
        )
    if guide.get("remainingStepCount") != expected["remainingStepCount"]:
        failures.append(
            f"{case['name']}: expected remaining step count {expected['remainingStepCount']}, got {guide.get('remainingStepCount')}."
        )
    if active_session.get("targetSkillId") != expected["targetSkillId"]:
        failures.append(
            f"{case['name']}: expected active target skill {expected['targetSkillId']}, got {active_session.get('targetSkillId')}."
        )

    return failures


def main() -> int:
    content = load_unit1_content()
    cases = _load_cases()
    learner_summary_cases = _load_learner_summary_cases()
    session_runner_cases = _load_session_runner_cases()
    evaluator_cases = _load_evaluator_cases()
    observation_submission_cases = _load_observation_submission_cases()
    session_history_summary_cases = _load_session_history_summary_cases()
    learner_record_cases = _load_learner_record_cases()
    session_planner_cases = _load_session_planner_cases()
    session_orchestrator_cases = _load_session_orchestrator_cases()
    active_session_cases = _load_active_session_cases()
    learner_record_submission_cases = _load_learner_record_submission_cases()
    failure_cases = _load_failure_cases()
    start_learning_session_cases = _load_start_learning_session_cases()

    failures: list[str] = []
    for case in cases:
        failures.extend(_assert_case(case, content))
    for case in learner_summary_cases:
        failures.extend(_assert_learner_summary_case(case, content))
    for case in session_runner_cases:
        failures.extend(_assert_session_runner_case(case))
    for case in evaluator_cases:
        failures.extend(_assert_evaluator_case(case, content))
    for case in observation_submission_cases:
        failures.extend(_assert_observation_submission_case(case, content))
    for case in session_history_summary_cases:
        failures.extend(_assert_session_history_summary_case(case, content))
    for case in learner_record_cases:
        failures.extend(_assert_learner_record_case(case, content))
    for case in session_planner_cases:
        failures.extend(_assert_session_planner_case(case))
    for case in session_orchestrator_cases:
        failures.extend(_assert_session_orchestrator_case(case))
    for case in active_session_cases:
        failures.extend(_assert_active_session_case(case))
    for case in learner_record_submission_cases:
        failures.extend(_assert_learner_record_submission_case(case, content))
    for case in failure_cases:
        failures.extend(_assert_failure_case(case, content))
    for case in start_learning_session_cases:
        failures.extend(_assert_start_learning_session_case(case))

    if failures:
        print("Harness failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Harness passed.")
    print(f"Single-event cases: {len(cases)}")
    print(f"Learner-summary cases: {len(learner_summary_cases)}")
    print(f"Session-runner cases: {len(session_runner_cases)}")
    print(f"Evaluator cases: {len(evaluator_cases)}")
    print(f"Observation-submission cases: {len(observation_submission_cases)}")
    print(f"Session-history summary cases: {len(session_history_summary_cases)}")
    print(f"Learner-record cases: {len(learner_record_cases)}")
    print(f"Session-planner cases: {len(session_planner_cases)}")
    print(f"Session-orchestrator cases: {len(session_orchestrator_cases)}")
    print(f"Active-session cases: {len(active_session_cases)}")
    print(f"Learner-record submission cases: {len(learner_record_submission_cases)}")
    print(f"Failure cases: {len(failure_cases)}")
    print(f"Start-learning-session cases: {len(start_learning_session_cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
