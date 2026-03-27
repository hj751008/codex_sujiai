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
