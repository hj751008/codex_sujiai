from __future__ import annotations


def plan_next_session(learner_record: dict) -> dict:
    recommendations = learner_record.get("latestRecommendations", [])
    learner_id = learner_record.get("learnerId")
    if not isinstance(recommendations, list) or not recommendations:
        raise ValueError("Learner record has no recommendations to plan from.")

    chosen = recommendations[0]
    payload = chosen.get("sessionPayload", {})
    steps = payload.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("Chosen recommendation does not contain a usable session payload.")

    return {
        "learnerId": learner_id,
        "plannedFromSkillId": chosen.get("targetSkillId"),
        "reasonCodes": chosen.get("reasonCodes", []),
        "recommendedNextSkillIds": chosen.get("recommendedNextSkillIds", []),
        "recommendedActivitySequence": chosen.get("recommendedActivitySequence", []),
        "sessionPayload": payload,
        "sessionPreview": {
            "stepCount": len(steps),
            "firstLessonStepId": steps[0].get("lessonStepId"),
            "firstQuestion": steps[0].get("firstTutorQuestion"),
        },
    }
