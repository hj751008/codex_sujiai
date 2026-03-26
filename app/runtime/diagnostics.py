from __future__ import annotations

from dataclasses import dataclass

from app.runtime.content_loader import UnitContent


SAFE_RESULTS = {"correct", "partial", "incorrect", "unknown"}
SAFE_CONFIDENCE_SIGNALS = {"confident", "hesitant", "unknown"}
PROVISIONAL_MASTERY_STATUSES = {
    "evidence_positive_but_unapproved",
    "developing",
    "needs_review",
    "insufficient_evidence",
}


@dataclass(frozen=True)
class DiagnosisResult:
    mastery: dict
    recommendations: list[dict]


@dataclass(frozen=True)
class LearnerSummaryResult:
    learnerId: str
    skillSummaries: list[dict]
    recommendations: list[dict]


def validate_evidence_event(event: dict) -> list[str]:
    errors: list[str] = []

    if not isinstance(event.get("eventId"), str) or not event["eventId"]:
        errors.append("Evidence input is missing a valid eventId.")
    if not isinstance(event.get("learnerId"), str) or not event["learnerId"]:
        errors.append("Evidence input is missing a valid learnerId.")
    if not isinstance(event.get("kind"), str) or not event["kind"]:
        errors.append("Evidence input is missing a valid kind.")

    result = event.get("result")
    if result not in SAFE_RESULTS:
        errors.append(f"Evidence input has unsupported result {result}.")

    confidence_signal = event.get("confidenceSignal", "unknown")
    if confidence_signal not in SAFE_CONFIDENCE_SIGNALS:
        errors.append(f"Evidence input has unsupported confidenceSignal {confidence_signal}.")

    error_pattern_ids = event.get("errorPatternIds", [])
    if not isinstance(error_pattern_ids, list):
        errors.append("Evidence input errorPatternIds must be a list.")

    observations = event.get("observations", [])
    if not isinstance(observations, list):
        errors.append("Evidence input observations must be a list.")

    return errors


def _build_indexes(
    content: UnitContent,
) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, dict], dict[str, list[dict]], dict[str, list[dict]], dict[str, dict]]:
    pattern_by_id = {record["id"]: record for record in content.error_patterns}

    recommendations_by_skill: dict[str, list[dict]] = {}
    for record in content.recommendation_examples:
        recommendations_by_skill.setdefault(record["recommend"], []).append(record)

    skills_by_id = {record["id"]: record for record in content.skills}
    prerequisites_by_target: dict[str, list[dict]] = {}
    for record in content.prerequisites:
        prerequisites_by_target.setdefault(record["targetSkillId"], []).append(record)

    activities_by_skill: dict[str, list[dict]] = {}
    for record in content.activity_recommendations:
        activities_by_skill.setdefault(record["skillId"], []).append(record)

    lesson_step_by_activity_id = {record["activityId"]: record for record in content.lesson_steps}

    return pattern_by_id, recommendations_by_skill, skills_by_id, prerequisites_by_target, activities_by_skill, lesson_step_by_activity_id


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _status_priority(status: str) -> int:
    priorities = {
        "developing": 0,
        "needs_review": 1,
        "insufficient_evidence": 2,
        "evidence_positive_but_unapproved": 3,
    }
    return priorities.get(status, 99)


def _resolve_target_skills(event: dict, pattern_by_id: dict[str, dict]) -> list[str]:
    target_skill_ids: list[str] = []

    skill_id = event.get("skillId")
    if isinstance(skill_id, str) and skill_id:
        target_skill_ids.append(skill_id)

    for pattern_id in event.get("errorPatternIds", []):
        pattern = pattern_by_id.get(pattern_id)
        if pattern:
            target_skill_ids.append(pattern["skillId"])

    return _ordered_unique(target_skill_ids)


def _resolve_primary_skill_id(target_skill_ids: list[str]) -> str | None:
    return target_skill_ids[0] if target_skill_ids else None


def _build_mastery(event: dict, primary_skill_id: str | None, matched_patterns: list[dict]) -> dict:
    result = event.get("result")
    event_id = event["eventId"]

    if primary_skill_id is None:
        status = "insufficient_evidence"
        explanations = [
            "The evidence does not yet resolve to a documented Unit 1 skill target.",
            "A reviewer should add a clearer skill link or a known error pattern before making a stronger judgment.",
        ]
    elif matched_patterns:
        status = "developing" if result in {"partial", "incorrect"} else "needs_review"
        explanations = [
            "Observed evidence matches one or more documented Unit 1 error patterns.",
            "Numeric thresholds and approved mastery labels are still undecided, so this remains a provisional judgment.",
        ]
    elif result == "correct":
        status = "evidence_positive_but_unapproved"
        explanations = [
            "The current event is positive evidence for the targeted skill.",
            "The repository does not yet approve a threshold for promoting this to mastered.",
        ]
    else:
        status = "needs_review"
        explanations = [
            "The event points to a skill, but there is not enough pattern-backed evidence for a stronger automated judgment.",
            "A reviewer should inspect the learner work before changing progression behavior.",
        ]

    return {
        "learnerId": event["learnerId"],
        "skillId": primary_skill_id,
        "status": status,
        "statusApproval": "provisional",
        "decisionType": "rule_assisted_conservative",
        "supportingEvidenceIds": [event_id],
        "matchedErrorPatternIds": [pattern["id"] for pattern in matched_patterns],
        "explanations": explanations,
        "blockedBy": [
            "mastery labels are not finalized in docs/mastery-rules.md",
            "minimum evidence required for pass remains UNDECIDED",
        ],
    }


def _recommendation_summary(skill_id: str, matched_patterns: list[dict], example_records: list[dict]) -> str:
    if example_records:
        return example_records[0]["when"]
    if matched_patterns:
        return matched_patterns[0]["summary"]
    return "Conservative follow-up practice is recommended pending more evidence."


def _serialize_activity(activity: dict) -> dict:
    return {
        "activityId": activity["activityId"],
        "skillId": activity["skillId"],
        "activityType": activity["activityType"],
        "title": activity["title"],
        "goal": activity["goal"],
        "firstTutorQuestion": activity["firstTutorQuestion"],
    }


def _serialize_session_step(activity: dict, lesson_step_by_activity_id: dict[str, dict]) -> dict:
    lesson_step = lesson_step_by_activity_id.get(activity["activityId"], {})
    return {
        "activityId": activity["activityId"],
        "lessonStepId": lesson_step.get("lessonStepId"),
        "skillId": activity["skillId"],
        "activityType": activity["activityType"],
        "title": activity["title"],
        "openingLine": lesson_step.get("openingLine"),
        "firstTutorQuestion": lesson_step.get("firstTutorQuestion", activity["firstTutorQuestion"]),
        "smallHint": lesson_step.get("smallHint"),
        "goodStoppingPoint": lesson_step.get("goodStoppingPoint"),
    }


def _ordered_unique_activity_ids(values: list[dict]) -> list[dict]:
    seen: set[str] = set()
    ordered: list[dict] = []
    for value in values:
        activity_id = value.get("activityId")
        if activity_id not in seen:
            seen.add(activity_id)
            ordered.append(value)
    return ordered


def _build_recommendations(
    event: dict,
    target_skill_ids: list[str],
    matched_patterns: list[dict],
    recommendations_by_skill: dict[str, list[dict]],
    skills_by_id: dict[str, dict],
    activities_by_skill: dict[str, list[dict]],
    lesson_step_by_activity_id: dict[str, dict],
) -> list[dict]:
    if not target_skill_ids:
        return []

    outputs: list[dict] = []

    for skill_id in target_skill_ids:
        example_records = recommendations_by_skill.get(skill_id, [])
        matched_for_skill = [pattern for pattern in matched_patterns if pattern["skillId"] == skill_id]
        skill_record = skills_by_id.get(skill_id, {})
        activity_records = activities_by_skill.get(skill_id, [])

        outputs.append(
            {
                "learnerId": event["learnerId"],
                "targetSkillId": skill_id,
                "targetSkillTitle": skill_record.get("title"),
                "recommendationType": "practice",
                "confidence": "limited",
                "needsReview": True,
                "reasonCodes": [
                    "documented_error_pattern_match" if matched_for_skill else "documented_skill_target",
                    "mastery_thresholds_not_approved",
                ],
                "summary": _recommendation_summary(skill_id, matched_for_skill, example_records),
                "sourceDocs": _ordered_unique(
                    [doc for pattern in matched_for_skill for doc in pattern.get("sourceDocs", [])]
                    + [doc for record in example_records for doc in record.get("sourceDocs", [])]
                    + [doc for activity in activity_records for doc in activity.get("sourceDocs", [])]
                ),
                "recommendedActivities": [_serialize_activity(activity) for activity in activity_records],
                "sessionPayload": {
                    "learnerId": event["learnerId"],
                    "targetSkillId": skill_id,
                    "steps": [
                        _serialize_session_step(activity, lesson_step_by_activity_id)
                        for activity in activity_records
                    ],
                },
            }
        )

    return outputs


def diagnose_event(content: UnitContent, event: dict) -> DiagnosisResult:
    pattern_by_id, recommendations_by_skill, skills_by_id, _, activities_by_skill, lesson_step_by_activity_id = _build_indexes(content)

    target_skill_ids = _resolve_target_skills(event, pattern_by_id)
    primary_skill_id = _resolve_primary_skill_id(target_skill_ids)
    matched_patterns = [
        pattern_by_id[pattern_id]
        for pattern_id in event.get("errorPatternIds", [])
        if pattern_id in pattern_by_id
    ]

    mastery = _build_mastery(event, primary_skill_id, matched_patterns)
    recommendations = _build_recommendations(
        event,
        target_skill_ids,
        matched_patterns,
        recommendations_by_skill,
        skills_by_id,
        activities_by_skill,
        lesson_step_by_activity_id,
    )

    return DiagnosisResult(mastery=mastery, recommendations=recommendations)


def _is_struggle_status(status: str) -> bool:
    return status in {"developing", "needs_review", "insufficient_evidence"}


def _prerequisite_priority(relationship: str) -> int:
    priorities = {
        "REQUIRED": 0,
        "HELPFUL": 1,
        "UNDECIDED": 2,
    }
    return priorities.get(relationship, 99)


def _build_prerequisite_blockers(
    skill_summaries_by_skill: dict[str, dict],
    prerequisites_by_target: dict[str, list[dict]],
) -> None:
    for skill_id, summary in skill_summaries_by_skill.items():
        links = prerequisites_by_target.get(skill_id, [])
        blockers: list[dict] = []

        for link in sorted(links, key=lambda item: (_prerequisite_priority(item["relationship"]), item["prerequisiteSkillId"])):
            prerequisite_skill_id = link["prerequisiteSkillId"]
            prerequisite_summary = skill_summaries_by_skill.get(prerequisite_skill_id)

            if prerequisite_summary and _is_struggle_status(prerequisite_summary["status"]):
                blockers.append(
                    {
                        "prerequisiteSkillId": prerequisite_skill_id,
                        "relationship": link["relationship"],
                        "approvalStatus": link["approvalStatus"],
                        "sourceDocs": link.get("sourceDocs", []),
                        "whyBlocked": (
                            f"Prerequisite skill {prerequisite_skill_id} is currently {prerequisite_summary['status']}, "
                            f"so progress on {skill_id} should stay conservative."
                        ),
                    }
                )
            elif prerequisite_summary is None:
                blockers.append(
                    {
                        "prerequisiteSkillId": prerequisite_skill_id,
                        "relationship": link["relationship"],
                        "approvalStatus": link["approvalStatus"],
                        "sourceDocs": link.get("sourceDocs", []),
                        "whyBlocked": (
                            f"Prerequisite skill {prerequisite_skill_id} does not yet have learner evidence, "
                            f"so progress on {skill_id} should stay conservative."
                        ),
                    }
                )

        summary["blockedByPrerequisites"] = blockers
        summary["hasRequiredPrerequisiteBlocker"] = any(
            blocker["relationship"] == "REQUIRED" for blocker in blockers
        )


def _append_prerequisite_reason_codes(
    recommendations_by_skill: dict[str, dict],
    skill_summaries_by_skill: dict[str, dict],
    activities_by_skill: dict[str, list[dict]],
    lesson_step_by_activity_id: dict[str, dict],
) -> None:
    for skill_id, recommendation in recommendations_by_skill.items():
        summary = skill_summaries_by_skill.get(skill_id)
        if not summary:
            continue

        blockers = summary.get("blockedByPrerequisites", [])
        if not blockers:
            recommendation["blockedByPrerequisites"] = []
            recommendation["recommendedNextSkillIds"] = [skill_id]
            recommendation["recommendedActivitySequence"] = recommendation.get("recommendedActivities", [])
            recommendation["sessionPayload"] = {
                "learnerId": recommendation["learnerId"],
                "targetSkillId": skill_id,
                "steps": [
                    _serialize_session_step(activity, lesson_step_by_activity_id)
                    for activity in recommendation.get("recommendedActivitySequence", [])
                ],
            }
            continue

        blocker_skill_ids = [blocker["prerequisiteSkillId"] for blocker in blockers]
        recommendation["blockedByPrerequisites"] = blockers
        recommendation["recommendedNextSkillIds"] = _ordered_unique(blocker_skill_ids + [skill_id])
        blocker_activities = [
            _serialize_activity(activity)
            for blocker_skill_id in blocker_skill_ids
            for activity in activities_by_skill.get(blocker_skill_id, [])
        ]
        recommendation["recommendedActivitySequence"] = _ordered_unique_activity_ids(
            blocker_activities + recommendation.get("recommendedActivities", [])
        )
        recommendation["sessionPayload"] = {
            "learnerId": recommendation["learnerId"],
            "targetSkillId": skill_id,
            "steps": [
                _serialize_session_step(activity, lesson_step_by_activity_id)
                for activity in recommendation.get("recommendedActivitySequence", [])
            ],
        }
        recommendation["reasonCodes"] = _ordered_unique(
            recommendation.get("reasonCodes", [])
            + [
                "required_prerequisite_blocker" if summary.get("hasRequiredPrerequisiteBlocker") else "helpful_prerequisite_blocker"
            ]
        )


def _sort_recommendations(recommendations: list[dict]) -> list[dict]:
    def sort_key(record: dict):
        blockers = record.get("blockedByPrerequisites", [])
        has_required = any(blocker["relationship"] == "REQUIRED" for blocker in blockers)
        has_any = bool(blockers)
        return (0 if has_required else 1 if has_any else 2, record["targetSkillId"])

    return sorted(recommendations, key=sort_key)


def summarize_learner(content: UnitContent, events: list[dict]) -> LearnerSummaryResult:
    if not events:
        raise ValueError("At least one event is required to summarize a learner.")

    learner_id = events[0].get("learnerId")
    if not isinstance(learner_id, str) or not learner_id:
        raise ValueError("Learner summary requires events with a valid learnerId.")

    _, _, _, prerequisites_by_target, activities_by_skill, lesson_step_by_activity_id = _build_indexes(content)

    event_results: list[DiagnosisResult] = []
    validation_errors: list[str] = []

    for event in events:
        if event.get("learnerId") != learner_id:
            raise ValueError("Learner summary events must all belong to the same learnerId.")

        errors = validate_evidence_event(event)
        if errors:
            validation_errors.extend(errors)
            continue

        event_results.append(diagnose_event(content, event))

    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    summaries_by_skill: dict[str, dict] = {}
    recommendations_by_skill: dict[str, dict] = {}

    for result in event_results:
        mastery = result.mastery
        skill_id = mastery.get("skillId")
        if not skill_id:
            continue

        summary = summaries_by_skill.setdefault(
            skill_id,
            {
                "learnerId": learner_id,
                "skillId": skill_id,
                "status": mastery["status"],
                "statusApproval": "provisional",
                "decisionType": "multi_event_rule_assisted_conservative",
                "supportingEvidenceIds": [],
                "matchedErrorPatternIds": [],
                "explanations": [],
                "blockedBy": list(mastery.get("blockedBy", [])),
                "eventCount": 0,
            },
        )

        if _status_priority(mastery["status"]) < _status_priority(summary["status"]):
            summary["status"] = mastery["status"]

        summary["eventCount"] += 1
        summary["supportingEvidenceIds"] = _ordered_unique(
            summary["supportingEvidenceIds"] + mastery.get("supportingEvidenceIds", [])
        )
        summary["matchedErrorPatternIds"] = _ordered_unique(
            summary["matchedErrorPatternIds"] + mastery.get("matchedErrorPatternIds", [])
        )
        summary["explanations"] = _ordered_unique(
            summary["explanations"] + mastery.get("explanations", [])
        )

        for recommendation in result.recommendations:
            target_skill_id = recommendation["targetSkillId"]
            stored = recommendations_by_skill.get(target_skill_id)
            if stored is None:
                recommendations_by_skill[target_skill_id] = {
                    **recommendation,
                    "sourceEventIds": list(mastery.get("supportingEvidenceIds", [])),
                }
                continue

            stored["sourceEventIds"] = _ordered_unique(
                stored.get("sourceEventIds", []) + mastery.get("supportingEvidenceIds", [])
            )
            stored["reasonCodes"] = _ordered_unique(
                stored.get("reasonCodes", []) + recommendation.get("reasonCodes", [])
            )
            stored["sourceDocs"] = _ordered_unique(
                stored.get("sourceDocs", []) + recommendation.get("sourceDocs", [])
            )

    _build_prerequisite_blockers(summaries_by_skill, prerequisites_by_target)
    _append_prerequisite_reason_codes(
        recommendations_by_skill,
        summaries_by_skill,
        activities_by_skill,
        lesson_step_by_activity_id,
    )

    skill_summaries = sorted(
        summaries_by_skill.values(),
        key=lambda record: (
            0 if record.get("hasRequiredPrerequisiteBlocker") else 1,
            _status_priority(record["status"]),
            record["skillId"],
        ),
    )
    recommendations = _sort_recommendations(list(recommendations_by_skill.values()))

    return LearnerSummaryResult(
        learnerId=learner_id,
        skillSummaries=skill_summaries,
        recommendations=recommendations,
    )
