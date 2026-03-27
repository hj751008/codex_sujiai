from __future__ import annotations

from copy import deepcopy

from app.runtime.diagnostics import summarize_learner
from app.runtime.session_runner import create_session_state
from app.runtime.session_runner import session_history_to_evidence_events, submit_observation


def create_learner_record(learner_id: str) -> dict:
    return {
        "learnerId": learner_id,
        "activeSession": None,
        "sessions": [],
        "evidenceEvents": [],
        "latestSkillSummaries": [],
        "latestRecommendations": [],
        "updatedAt": None,
    }


def validate_learner_record(learner_record: dict) -> list[str]:
    errors: list[str] = []
    learner_id = learner_record.get("learnerId")
    if not isinstance(learner_id, str) or not learner_id:
        errors.append("learnerRecord.learnerId must be a non-empty string.")

    active_session = learner_record.get("activeSession")
    if active_session is not None:
        errors.extend(_validate_session_like(active_session, learner_id, "activeSession"))

    sessions = learner_record.get("sessions", [])
    if not isinstance(sessions, list):
        errors.append("learnerRecord.sessions must be a list.")
    else:
        for index, session in enumerate(sessions):
            if not isinstance(session, dict):
                errors.append(f"learnerRecord.sessions[{index}] must be an object.")
                continue
            errors.extend(_validate_session_like(session, learner_id, f"sessions[{index}]"))

    return errors


def _session_snapshot(session_state: dict) -> dict:
    return {
        "learnerId": session_state.get("learnerId"),
        "targetSkillId": session_state.get("targetSkillId"),
        "status": session_state.get("status"),
        "currentStepIndex": session_state.get("currentStepIndex"),
        "currentStep": deepcopy(session_state.get("currentStep")),
        "nextStep": deepcopy(session_state.get("nextStep")),
        "completedStepIds": list(session_state.get("completedStepIds", [])),
        "remainingStepIds": list(session_state.get("remainingStepIds", [])),
        "steps": deepcopy(session_state.get("steps", [])),
        "completionRule": session_state.get("completionRule"),
        "lastEvaluation": deepcopy(session_state.get("lastEvaluation")),
        "history": deepcopy(session_state.get("history", [])),
    }


def merge_session_into_learner_record(learner_record: dict, session_state: dict, content) -> dict:
    learner_id = learner_record.get("learnerId")
    if learner_id != session_state.get("learnerId"):
        raise ValueError("Learner record and session state must belong to the same learnerId.")

    new_events = session_history_to_evidence_events(session_state)
    existing_events = list(learner_record.get("evidenceEvents", []))
    seen_event_ids = {event.get("eventId") for event in existing_events}
    merged_events = existing_events + [event for event in new_events if event.get("eventId") not in seen_event_ids]

    summary = summarize_learner(content, merged_events) if merged_events else None

    merged_record = {
        **learner_record,
        "activeSession": None if session_state.get("status") == "completed" else _session_snapshot(session_state),
        "sessions": _upsert_session_snapshot(list(learner_record.get("sessions", [])), session_state),
        "evidenceEvents": merged_events,
        "latestSkillSummaries": [] if summary is None else summary.skillSummaries,
        "latestRecommendations": [] if summary is None else summary.recommendations,
        "updatedAt": _latest_timestamp(session_state),
    }
    return merged_record


def _latest_timestamp(session_state: dict) -> str | None:
    history = session_state.get("history", [])
    timestamps = [record.get("timestamp") for record in history if isinstance(record.get("timestamp"), str)]
    return timestamps[-1] if timestamps else None


def store_active_session(learner_record: dict, orchestration_result: dict) -> dict:
    learner_id = learner_record.get("learnerId")
    if learner_id != orchestration_result.get("learnerId"):
        raise ValueError("Learner record and orchestration result must belong to the same learnerId.")

    action = orchestration_result.get("action")
    if action == "resume_session":
        active_session = orchestration_result.get("sessionState")
    elif action == "plan_new_session":
        planned_session = orchestration_result.get("plannedSession", {})
        payload = planned_session.get("sessionPayload", {})
        active_session = create_session_state(
            {
                "learnerId": learner_id,
                "targetSkillId": payload.get("targetSkillId"),
                "sessionPayload": payload,
            }
        )
    else:
        raise ValueError(f"Unsupported orchestration action: {action}")

    return {
        **learner_record,
        "activeSession": _session_snapshot(active_session),
    }


def submit_observation_to_learner_record(learner_record: dict, observation_form: dict, content) -> dict:
    validation_errors = validate_learner_record(learner_record)
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    learner_record = _ensure_active_session(learner_record)
    active_session = learner_record.get("activeSession")
    if not isinstance(active_session, dict):
        raise ValueError("Learner record has no activeSession to submit an observation against.")

    learner_id = learner_record.get("learnerId")
    if learner_id != active_session.get("learnerId"):
        raise ValueError("Learner record activeSession must belong to the same learnerId.")

    updated_session = submit_observation(
        active_session,
        observation_form,
        content.evaluator_rubrics,
        content.observation_form_mappings,
    )
    return merge_session_into_learner_record(learner_record, updated_session, content)


def run_learning_turn(learner_record: dict, observation_form: dict, content) -> dict:
    updated_record = submit_observation_to_learner_record(learner_record, observation_form, content)
    active_session = updated_record.get("activeSession")
    latest_recommendations = updated_record.get("latestRecommendations", [])
    latest_sessions = updated_record.get("sessions", [])
    latest_session = latest_sessions[-1] if latest_sessions else None
    last_history = None
    if isinstance(latest_session, dict):
        history = latest_session.get("history", [])
        if isinstance(history, list) and history:
            last_history = history[-1]

    evaluation = last_history.get("evaluation", {}) if isinstance(last_history, dict) else {}
    turn_summary = {
        "learnerId": updated_record.get("learnerId"),
        "submittedLessonStepId": None if not isinstance(last_history, dict) else last_history.get("lessonStepId"),
        "decision": evaluation.get("decision"),
        "sessionStatus": "completed" if active_session is None else active_session.get("status"),
        "completedStepIds": [] if not isinstance(latest_session, dict) else latest_session.get("completedStepIds", []),
        "latestRecommendationSkillIds": [
            record.get("targetSkillId")
            for record in latest_recommendations
            if isinstance(record, dict)
        ],
    }

    if isinstance(active_session, dict):
        current_step = active_session.get("currentStep") or {}
        next_step = active_session.get("nextStep") or {}
        turn_summary["nextAction"] = "continue_active_session"
        turn_summary["nextStepGuide"] = {
            "targetSkillId": active_session.get("targetSkillId"),
            "currentLessonStepId": current_step.get("lessonStepId"),
            "currentActivityId": current_step.get("activityId"),
            "title": current_step.get("title"),
            "openingLine": current_step.get("openingLine"),
            "firstTutorQuestion": current_step.get("firstTutorQuestion"),
            "smallHint": current_step.get("smallHint"),
            "goodStoppingPoint": current_step.get("goodStoppingPoint"),
            "watchFor": current_step.get("watchFor"),
            "exampleTutorMove": current_step.get("exampleTutorMove"),
            "exampleLearnerResponse": current_step.get("exampleLearnerResponse"),
            "nextLessonStepId": next_step.get("lessonStepId"),
            "remainingStepCount": len(active_session.get("remainingStepIds", [])),
        }
    else:
        next_recommendation = latest_recommendations[0] if latest_recommendations else {}
        payload = next_recommendation.get("sessionPayload", {}) if isinstance(next_recommendation, dict) else {}
        steps = payload.get("steps", []) if isinstance(payload, dict) else []
        first_step = steps[0] if steps and isinstance(steps[0], dict) else {}
        turn_summary["nextAction"] = "review_next_recommendation"
        turn_summary["nextRecommendedSession"] = {
            "targetSkillId": None if not isinstance(next_recommendation, dict) else next_recommendation.get("targetSkillId"),
            "firstLessonStepId": first_step.get("lessonStepId"),
            "firstTutorQuestion": first_step.get("firstTutorQuestion"),
            "watchFor": first_step.get("watchFor"),
            "exampleTutorMove": first_step.get("exampleTutorMove"),
            "stepCount": len(steps) if isinstance(steps, list) else 0,
        }

    return {
        "learnerId": updated_record.get("learnerId"),
        "turnSummary": turn_summary,
        "learnerRecord": updated_record,
    }


def _ensure_active_session(learner_record: dict) -> dict:
    active_session = learner_record.get("activeSession")
    if isinstance(active_session, dict):
        return learner_record

    sessions = learner_record.get("sessions", [])
    if not isinstance(sessions, list):
        return learner_record

    for session in reversed(sessions):
        if not isinstance(session, dict):
            continue
        if session.get("status") != "in_progress":
            continue
        if session.get("currentStep") is None:
            continue
        if not isinstance(session.get("steps"), list) or not session.get("steps"):
            continue
        return {
            **learner_record,
            "activeSession": _session_snapshot(session),
        }

    return learner_record


def _upsert_session_snapshot(existing_sessions: list[dict], session_state: dict) -> list[dict]:
    snapshot = _session_snapshot(session_state)
    state_step_ids = _session_step_ids(session_state)

    for index in range(len(existing_sessions) - 1, -1, -1):
        existing = existing_sessions[index]
        if not isinstance(existing, dict):
            continue
        if existing.get("learnerId") != session_state.get("learnerId"):
            continue
        if existing.get("targetSkillId") != session_state.get("targetSkillId"):
            continue
        if _session_step_ids(existing) != state_step_ids:
            continue

        updated_sessions = list(existing_sessions)
        updated_sessions[index] = snapshot
        return updated_sessions

    return existing_sessions + [snapshot]


def _session_step_ids(session_like: dict) -> list[str]:
    steps = session_like.get("steps", [])
    if not isinstance(steps, list):
        return []
    return [step.get("lessonStepId") for step in steps if isinstance(step, dict)]


def _validate_session_like(session_like: dict, learner_id: str | None, label: str) -> list[str]:
    errors: list[str] = []
    if session_like.get("learnerId") != learner_id:
        errors.append(f"learnerRecord.{label}.learnerId must match learnerRecord.learnerId.")

    steps = session_like.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append(f"learnerRecord.{label}.steps must be a non-empty list.")
        return errors

    current_step_index = session_like.get("currentStepIndex")
    if not isinstance(current_step_index, int) or not (0 <= current_step_index < len(steps)):
        errors.append(f"learnerRecord.{label}.currentStepIndex must point to an existing step.")
        return errors

    current_step = session_like.get("currentStep")
    expected_current = steps[current_step_index]
    expected_current_id = expected_current.get("lessonStepId") if isinstance(expected_current, dict) else None
    current_step_id = current_step.get("lessonStepId") if isinstance(current_step, dict) else None
    if current_step_id != expected_current_id:
        errors.append(f"learnerRecord.{label}.currentStep must match steps[currentStepIndex].")

    next_step = session_like.get("nextStep")
    expected_next = steps[current_step_index + 1] if current_step_index + 1 < len(steps) else None
    expected_next_id = expected_next.get("lessonStepId") if isinstance(expected_next, dict) else None
    next_step_id = next_step.get("lessonStepId") if isinstance(next_step, dict) else None
    if next_step_id != expected_next_id:
        errors.append(f"learnerRecord.{label}.nextStep must match the next step in sequence or be null at the end.")

    remaining_step_ids = session_like.get("remainingStepIds")
    if not isinstance(remaining_step_ids, list):
        errors.append(f"learnerRecord.{label}.remainingStepIds must be a list.")
    else:
        expected_remaining = [
            step.get("lessonStepId")
            for step in steps[current_step_index:]
            if isinstance(step, dict)
        ]
        if remaining_step_ids != expected_remaining:
            errors.append(f"learnerRecord.{label}.remainingStepIds must match the remaining steps from currentStepIndex.")

    return errors
