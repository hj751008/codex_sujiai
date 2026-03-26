from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "app" / "content" / "unit1-prime-factorization"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def add_error(errors: list[str], message: str) -> None:
    errors.append(message)


def require_source_docs(record: dict, label: str, errors: list[str]) -> None:
    source_docs = record.get("sourceDocs")
    if not isinstance(source_docs, list) or not source_docs:
        add_error(errors, f"{label} is missing non-empty sourceDocs.")


def reject_threshold_like_fields(record: dict, label: str, errors: list[str]) -> None:
    banned_keys = {
        "threshold",
        "thresholds",
        "score",
        "scores",
        "cutoff",
        "cutoffs",
        "minimumEvidence",
        "retryRule",
        "overrideRule",
    }
    overlap = banned_keys.intersection(record.keys())
    if overlap:
        names = ", ".join(sorted(overlap))
        add_error(errors, f"{label} contains threshold-like fields that are not approved: {names}.")


def validate_skills(skills: list[dict], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    skill_ids: set[str] = set()

    for record in skills:
        skill_id = record.get("id")
        if not isinstance(skill_id, str) or not skill_id:
            add_error(errors, "Skill record is missing a valid id.")
            continue
        if skill_id in seen:
            add_error(errors, f"Duplicate skill id found: {skill_id}.")
        seen.add(skill_id)
        skill_ids.add(skill_id)

        require_source_docs(record, f"Skill {skill_id}", errors)
        reject_threshold_like_fields(record, f"Skill {skill_id}", errors)

        parent_skill_id = record.get("parentSkillId")
        if parent_skill_id is not None and not isinstance(parent_skill_id, str):
            add_error(errors, f"Skill {skill_id} has an invalid parentSkillId.")

    for record in skills:
        skill_id = record.get("id")
        parent_skill_id = record.get("parentSkillId")
        if parent_skill_id and parent_skill_id not in skill_ids:
            add_error(errors, f"Skill {skill_id} references unknown parentSkillId {parent_skill_id}.")

    return skill_ids


def validate_prerequisites(prerequisites: list[dict], skill_ids: set[str], errors: list[str]) -> None:
    for index, record in enumerate(prerequisites, start=1):
        label = f"Prerequisite record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        prereq_id = record.get("prerequisiteSkillId")
        target_id = record.get("targetSkillId")
        relationship = record.get("relationship")
        approval_status = record.get("approvalStatus")

        if prereq_id not in skill_ids:
            add_error(errors, f"{label} references unknown prerequisiteSkillId {prereq_id}.")
        if target_id not in skill_ids:
            add_error(errors, f"{label} references unknown targetSkillId {target_id}.")
        if relationship not in {"REQUIRED", "HELPFUL", "UNDECIDED"}:
            add_error(errors, f"{label} has unsupported relationship {relationship}.")
        if approval_status not in {"approved", "provisional", "draft-from-docs", "UNDECIDED"}:
            add_error(errors, f"{label} is missing a safe approvalStatus.")


def validate_recommendations(recommendations: list[dict], skill_ids: set[str], errors: list[str]) -> None:
    for index, record in enumerate(recommendations, start=1):
        label = f"Recommendation record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        target_id = record.get("recommend")
        confidence = record.get("confidence")
        needs_review = record.get("needsReview")

        if target_id not in skill_ids:
            add_error(errors, f"{label} recommends unknown skill id {target_id}.")
        if confidence not in {"limited", "moderate", "high", "UNDECIDED"}:
            add_error(errors, f"{label} has unsupported confidence value {confidence}.")
        if not isinstance(needs_review, bool):
            add_error(errors, f"{label} must include a boolean needsReview flag.")


def validate_error_patterns(error_patterns: list[dict], skill_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()

    for index, record in enumerate(error_patterns, start=1):
        label = f"Error pattern record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        pattern_id = record.get("id")
        skill_id = record.get("skillId")

        if not isinstance(pattern_id, str) or not pattern_id:
            add_error(errors, f"{label} is missing a valid id.")
        elif pattern_id in seen:
            add_error(errors, f"Duplicate error pattern id found: {pattern_id}.")
        else:
            seen.add(pattern_id)

        if skill_id not in skill_ids:
            add_error(errors, f"{label} references unknown skillId {skill_id}.")


def validate_activity_recommendations(activities: list[dict], skill_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()

    for index, record in enumerate(activities, start=1):
        label = f"Activity recommendation record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        activity_id = record.get("activityId")
        skill_id = record.get("skillId")
        activity_type = record.get("activityType")

        if not isinstance(activity_id, str) or not activity_id:
            add_error(errors, f"{label} is missing a valid activityId.")
        elif activity_id in seen:
            add_error(errors, f"Duplicate activityId found: {activity_id}.")
        else:
            seen.add(activity_id)

        if skill_id not in skill_ids:
            add_error(errors, f"{label} references unknown skillId {skill_id}.")
        if activity_type not in {"dialogue-flow", "worked-bridge"}:
            add_error(errors, f"{label} has unsupported activityType {activity_type}.")


def validate_lesson_steps(lesson_steps: list[dict], activity_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()

    for index, record in enumerate(lesson_steps, start=1):
        label = f"Lesson step record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        lesson_step_id = record.get("lessonStepId")
        activity_id = record.get("activityId")

        if not isinstance(lesson_step_id, str) or not lesson_step_id:
            add_error(errors, f"{label} is missing a valid lessonStepId.")
        elif lesson_step_id in seen:
            add_error(errors, f"Duplicate lessonStepId found: {lesson_step_id}.")
        else:
            seen.add(lesson_step_id)

        if activity_id not in activity_ids:
            add_error(errors, f"{label} references unknown activityId {activity_id}.")


def validate_evaluator_rubrics(rubrics: list[dict], lesson_step_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()

    for index, record in enumerate(rubrics, start=1):
        label = f"Evaluator rubric record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        lesson_step_id = record.get("lessonStepId")
        required_signals = record.get("requiredSignals")

        if lesson_step_id not in lesson_step_ids:
            add_error(errors, f"{label} references unknown lessonStepId {lesson_step_id}.")
        elif lesson_step_id in seen:
            add_error(errors, f"Duplicate evaluator rubric lessonStepId found: {lesson_step_id}.")
        else:
            seen.add(lesson_step_id)

        if not isinstance(required_signals, list) or not required_signals:
            add_error(errors, f"{label} must include a non-empty requiredSignals list.")


def validate_observation_form_mappings(mappings: list[dict], lesson_step_ids: set[str], errors: list[str]) -> None:
    seen: set[str] = set()

    for index, record in enumerate(mappings, start=1):
        label = f"Observation form mapping record #{index}"
        require_source_docs(record, label, errors)
        reject_threshold_like_fields(record, label, errors)

        lesson_step_id = record.get("lessonStepId")
        fields = record.get("fields")

        if lesson_step_id not in lesson_step_ids:
            add_error(errors, f"{label} references unknown lessonStepId {lesson_step_id}.")
        elif lesson_step_id in seen:
            add_error(errors, f"Duplicate observation form mapping lessonStepId found: {lesson_step_id}.")
        else:
            seen.add(lesson_step_id)

        if not isinstance(fields, list) or not fields:
            add_error(errors, f"{label} must include a non-empty fields list.")


def main() -> int:
    errors: list[str] = []

    skills = load_json(CONTENT_DIR / "skills.json")
    prerequisites = load_json(CONTENT_DIR / "prerequisites.json")
    recommendations = load_json(CONTENT_DIR / "recommendation-examples.json")
    error_patterns = load_json(CONTENT_DIR / "error-patterns.json")
    activities = load_json(CONTENT_DIR / "activity-recommendations.json")
    lesson_steps = load_json(CONTENT_DIR / "lesson-steps.json")
    evaluator_rubrics = load_json(CONTENT_DIR / "evaluator-rubrics.json")
    observation_form_mappings = load_json(CONTENT_DIR / "observation-form-mappings.json")

    skill_ids = validate_skills(skills, errors)
    validate_prerequisites(prerequisites, skill_ids, errors)
    validate_recommendations(recommendations, skill_ids, errors)
    validate_error_patterns(error_patterns, skill_ids, errors)
    validate_activity_recommendations(activities, skill_ids, errors)
    activity_ids = {record["activityId"] for record in activities if isinstance(record.get("activityId"), str)}
    validate_lesson_steps(lesson_steps, activity_ids, errors)
    lesson_step_ids = {record["lessonStepId"] for record in lesson_steps if isinstance(record.get("lessonStepId"), str)}
    validate_evaluator_rubrics(evaluator_rubrics, lesson_step_ids, errors)
    validate_observation_form_mappings(observation_form_mappings, lesson_step_ids, errors)

    if errors:
        print("Validation failed:")
        for message in errors:
            print(f"- {message}")
        return 1

    print("Validation passed.")
    print(f"Skills: {len(skills)}")
    print(f"Prerequisite links: {len(prerequisites)}")
    print(f"Recommendation examples: {len(recommendations)}")
    print(f"Error patterns: {len(error_patterns)}")
    print(f"Activity recommendations: {len(activities)}")
    print(f"Lesson steps: {len(lesson_steps)}")
    print(f"Evaluator rubrics: {len(evaluator_rubrics)}")
    print(f"Observation form mappings: {len(observation_form_mappings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
