from __future__ import annotations

from copy import deepcopy

from app.runtime.learner_record import store_active_session
from app.runtime.session_planner import plan_next_session


def resume_or_plan_session(learner_record: dict) -> dict:
    learner_id = learner_record.get("learnerId")
    sessions = learner_record.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("Learner record sessions must be a list.")

    resumable_session = _find_resumable_session(sessions)
    if resumable_session is not None:
        current_step = resumable_session.get("currentStep") or {}
        remaining_step_ids = resumable_session.get("remainingStepIds", [])
        return {
            "learnerId": learner_id,
            "action": "resume_session",
            "sessionState": deepcopy(resumable_session),
            "resumePreview": {
                "targetSkillId": resumable_session.get("targetSkillId"),
                "currentLessonStepId": current_step.get("lessonStepId"),
                "remainingStepCount": len(remaining_step_ids),
                "completedStepCount": len(resumable_session.get("completedStepIds", [])),
            },
        }

    planned_session = plan_next_session(learner_record)
    return {
        "learnerId": learner_id,
        "action": "plan_new_session",
        "plannedSession": planned_session,
    }


def start_learning_session(learner_record: dict) -> dict:
    orchestration_result = resume_or_plan_session(learner_record)
    updated_record = store_active_session(learner_record, orchestration_result)
    active_session = updated_record.get("activeSession")
    if not isinstance(active_session, dict):
        raise ValueError("Start-learning-session could not create or recover an active session.")

    current_step = active_session.get("currentStep") or {}
    next_step = active_session.get("nextStep") or {}

    return {
        "learnerId": updated_record.get("learnerId"),
        "action": orchestration_result.get("action"),
        "activeSession": active_session,
        "sessionStartGuide": {
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
        },
        "learnerRecord": updated_record,
    }


def _find_resumable_session(sessions: list[dict]) -> dict | None:
    for session in reversed(sessions):
        if not isinstance(session, dict):
            continue
        if session.get("status") != "in_progress":
            continue
        if session.get("currentStep") is None:
            continue
        if not isinstance(session.get("steps"), list) or not session.get("steps"):
            continue
        return session
    return None
