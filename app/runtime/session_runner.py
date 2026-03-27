from __future__ import annotations


def build_observation_form_template(session_state: dict, observation_form_mappings: list[dict]) -> dict:
    current_step = session_state.get("currentStep")
    if current_step is None:
        raise ValueError("Session state has no current step.")

    lesson_step_id = current_step.get("lessonStepId")
    mapping = next((record for record in observation_form_mappings if record.get("lessonStepId") == lesson_step_id), None)
    if mapping is None:
        raise ValueError(f"No observation form mapping found for lesson step {lesson_step_id}.")

    learner_response_prompt = mapping.get("learnerResponsePrompt")
    tutor_note_prompt = mapping.get("tutorNotePrompt")
    fields = mapping.get("fields", [])
    if not isinstance(learner_response_prompt, str) or not learner_response_prompt.strip():
        raise ValueError(f"Observation form mapping for {lesson_step_id} is missing learnerResponsePrompt.")
    if not isinstance(tutor_note_prompt, str) or not tutor_note_prompt.strip():
        raise ValueError(f"Observation form mapping for {lesson_step_id} is missing tutorNotePrompt.")
    if not isinstance(fields, list) or not fields:
        raise ValueError(f"Observation form mapping for {lesson_step_id} must contain at least one field.")

    normalized_fields = []
    for field in fields:
        field_id = field.get("fieldId")
        label = field.get("label")
        prompt = field.get("prompt")
        true_means = field.get("trueMeans")
        if not isinstance(field_id, str) or not field_id.strip():
            raise ValueError(f"Observation form mapping for {lesson_step_id} contains a field without fieldId.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Observation form mapping for {lesson_step_id}:{field_id} is missing label.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Observation form mapping for {lesson_step_id}:{field_id} is missing prompt.")
        if not isinstance(true_means, str) or not true_means.strip():
            raise ValueError(f"Observation form mapping for {lesson_step_id}:{field_id} is missing trueMeans.")
        normalized_fields.append(
            {
                "fieldId": field_id,
                "label": label,
                "prompt": prompt,
                "trueMeans": true_means,
            }
        )

    return {
        "lessonStepId": lesson_step_id,
        "learnerResponsePrompt": learner_response_prompt,
        "tutorNotePrompt": tutor_note_prompt,
        "fields": normalized_fields,
    }


def create_observation_record(session_state: dict, observation_form: dict, evaluation_result: dict) -> dict:
    current_step = session_state.get("currentStep")
    if current_step is None:
        raise ValueError("Session state has no current step.")

    return {
        "attemptIndex": len(session_state.get("history", [])),
        "lessonStepId": current_step.get("lessonStepId"),
        "activityId": current_step.get("activityId"),
        "learnerResponse": observation_form.get("learnerResponse", ""),
        "fieldValues": observation_form.get("fieldValues", {}),
        "tutorNote": observation_form.get("tutorNote"),
        "timestamp": observation_form.get("timestamp"),
        "evaluation": evaluation_result,
    }


def observation_form_to_evaluation_input(session_state: dict, observation_form: dict, observation_form_mappings: list[dict]) -> dict:
    current_step = session_state.get("currentStep")
    if current_step is None:
        raise ValueError("Session state has no current step.")

    lesson_step_id = current_step.get("lessonStepId")
    mapping = next((record for record in observation_form_mappings if record.get("lessonStepId") == lesson_step_id), None)
    if mapping is None:
        raise ValueError(f"No observation form mapping found for lesson step {lesson_step_id}.")

    field_values = observation_form.get("fieldValues", {})
    learner_response = observation_form.get("learnerResponse", "")
    if not isinstance(field_values, dict):
        raise ValueError("Observation form fieldValues must be an object.")
    if not isinstance(learner_response, str):
        raise ValueError("Observation form learnerResponse must be a string.")

    observed_signals: list[str] = []
    for field in mapping.get("fields", []):
        field_id = field.get("fieldId")
        if field_values.get(field_id) is True:
            observed_signals.append(field.get("signalOnTrue"))

    return {
        "learnerResponse": learner_response,
        "observedSignals": [signal for signal in observed_signals if isinstance(signal, str)],
    }


def create_session_state(recommendation: dict) -> dict:
    payload = recommendation.get("sessionPayload", {})
    steps = payload.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("Recommendation does not contain a usable sessionPayload.steps sequence.")

    first_step = steps[0]
    return {
        "learnerId": recommendation.get("learnerId"),
        "targetSkillId": recommendation.get("targetSkillId"),
        "status": "in_progress",
        "currentStepIndex": 0,
        "currentStep": first_step,
        "nextStep": steps[1] if len(steps) > 1 else None,
        "completedStepIds": [],
        "remainingStepIds": [step.get("lessonStepId") for step in steps],
        "steps": steps,
        "completionRule": "complete_all_steps_in_order",
        "history": [],
    }


def evaluate_current_step(session_state: dict, evaluation_input: dict, evaluator_rubrics: list[dict]) -> dict:
    current_step = session_state.get("currentStep")
    if current_step is None:
        raise ValueError("Session state has no current step to evaluate.")

    lesson_step_id = current_step.get("lessonStepId")
    rubric = next((record for record in evaluator_rubrics if record.get("lessonStepId") == lesson_step_id), None)
    if rubric is None:
        raise ValueError(f"No evaluator rubric found for lesson step {lesson_step_id}.")

    observed_signals = evaluation_input.get("observedSignals", [])
    learner_response = evaluation_input.get("learnerResponse", "")
    if not isinstance(observed_signals, list):
        raise ValueError("Evaluation input observedSignals must be a list.")
    if not isinstance(learner_response, str):
        raise ValueError("Evaluation input learnerResponse must be a string.")

    required_signals = rubric.get("requiredSignals", [])
    matched_required_signals = [signal for signal in required_signals if signal in observed_signals]
    missing_required_signals = [signal for signal in required_signals if signal not in observed_signals]

    lowered_response = learner_response.lower()
    matched_text_hints = [
        hint for hint in rubric.get("optionalTextHints", []) if isinstance(hint, str) and hint.lower() in lowered_response
    ]

    if not missing_required_signals:
        decision = "completed"
    elif matched_required_signals or matched_text_hints:
        decision = "needs_follow_up"
    else:
        decision = "uncertain"

    return {
        "lessonStepId": lesson_step_id,
        "decision": decision,
        "matchedRequiredSignals": matched_required_signals,
        "missingRequiredSignals": missing_required_signals,
        "matchedTextHints": matched_text_hints,
        "canAutoAdvance": decision == "completed",
    }


def apply_evaluator_decision(session_state: dict, evaluation_result: dict) -> dict:
    if evaluation_result.get("decision") != "completed":
        return {
            **session_state,
            "lastEvaluation": evaluation_result,
        }

    advanced_state = advance_session_state(session_state, evaluation_result["lessonStepId"])
    return {
        **advanced_state,
        "lastEvaluation": evaluation_result,
    }


def submit_observation(
    session_state: dict,
    observation_form: dict,
    evaluator_rubrics: list[dict],
    observation_form_mappings: list[dict],
) -> dict:
    evaluation_input = observation_form_to_evaluation_input(session_state, observation_form, observation_form_mappings)
    evaluation_result = evaluate_current_step(session_state, evaluation_input, evaluator_rubrics)
    observation_record = create_observation_record(session_state, observation_form, evaluation_result)

    updated_state = apply_evaluator_decision(session_state, evaluation_result)
    history = list(updated_state.get("history", []))
    history.append(observation_record)

    return {
        **updated_state,
        "history": history,
    }


def session_history_to_evidence_events(session_state: dict) -> list[dict]:
    learner_id = session_state.get("learnerId")
    history = session_state.get("history", [])
    if not isinstance(history, list):
        raise ValueError("Session state history must be a list.")

    events: list[dict] = []
    for record in history:
        evaluation = record.get("evaluation", {})
        lesson_step_id = record.get("lessonStepId")
        activity_skill_id = record.get("activityId")

        # Activity ids are namespaced by skill, so recover the skill id conservatively.
        # Example: ACT-U1-S3-REWRITE-CLEANLY -> U1-S3
        recovered_skill_id = None
        if isinstance(activity_skill_id, str) and activity_skill_id.startswith("ACT-"):
            parts = activity_skill_id.split("-")
            if len(parts) >= 3:
                recovered_skill_id = "-".join(parts[1:3])

        decision = evaluation.get("decision")
        if decision == "completed":
            result = "correct"
        elif decision == "needs_follow_up":
            result = "partial"
        else:
            result = "unknown"

        matched_signals = evaluation.get("matchedRequiredSignals", [])
        missing_signals = evaluation.get("missingRequiredSignals", [])
        observations = []
        if record.get("learnerResponse"):
            observations.append(record["learnerResponse"])
        if record.get("tutorNote"):
            observations.append(record["tutorNote"])
        if missing_signals:
            observations.append(f"Missing required signals: {', '.join(missing_signals)}")

        events.append(
            {
                "eventId": f"session-history-{record.get('attemptIndex', 0)}-{lesson_step_id}",
                "learnerId": learner_id,
                "kind": "session_history_observation",
                "skillId": recovered_skill_id,
                "result": result,
                "errorPatternIds": [],
                "observations": observations,
                "confidenceSignal": "hesitant" if decision != "completed" else "confident",
                "sourceDocs": [],
                "derivedFrom": {
                    "lessonStepId": lesson_step_id,
                    "activityId": activity_skill_id,
                    "matchedRequiredSignals": matched_signals,
                    "missingRequiredSignals": missing_signals,
                },
            }
        )

    return events


def advance_session_state(session_state: dict, completed_lesson_step_id: str) -> dict:
    steps = session_state.get("steps", [])
    current_step_index = session_state.get("currentStepIndex")

    if session_state.get("status") == "completed":
        raise ValueError("Session is already completed.")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Session state is missing steps.")
    if not isinstance(current_step_index, int) or current_step_index < 0 or current_step_index >= len(steps):
        raise ValueError("Session state has an invalid currentStepIndex.")

    current_step = steps[current_step_index]
    expected_lesson_step_id = current_step.get("lessonStepId")
    if completed_lesson_step_id != expected_lesson_step_id:
        raise ValueError(
            f"Cannot complete lesson step {completed_lesson_step_id}; current step is {expected_lesson_step_id}."
        )

    completed_step_ids = list(session_state.get("completedStepIds", []))
    completed_step_ids.append(completed_lesson_step_id)

    next_index = current_step_index + 1
    is_completed = next_index >= len(steps)

    return {
        **session_state,
        "status": "completed" if is_completed else "in_progress",
        "currentStepIndex": next_index if not is_completed else current_step_index,
        "currentStep": None if is_completed else steps[next_index],
        "nextStep": None if is_completed or next_index + 1 >= len(steps) else steps[next_index + 1],
        "completedStepIds": completed_step_ids,
        "remainingStepIds": [step.get("lessonStepId") for step in steps[next_index:]] if not is_completed else [],
    }
