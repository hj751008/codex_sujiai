from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
UNIT1_DIR = APP_ROOT / "content" / "unit1-prime-factorization"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class UnitContent:
    skills: list[dict]
    prerequisites: list[dict]
    recommendation_examples: list[dict]
    error_patterns: list[dict]
    activity_recommendations: list[dict]
    lesson_steps: list[dict]
    evaluator_rubrics: list[dict]
    observation_form_mappings: list[dict]


def load_unit1_content() -> UnitContent:
    return UnitContent(
        skills=_load_json(UNIT1_DIR / "skills.json"),
        prerequisites=_load_json(UNIT1_DIR / "prerequisites.json"),
        recommendation_examples=_load_json(UNIT1_DIR / "recommendation-examples.json"),
        error_patterns=_load_json(UNIT1_DIR / "error-patterns.json"),
        activity_recommendations=_load_json(UNIT1_DIR / "activity-recommendations.json"),
        lesson_steps=_load_json(UNIT1_DIR / "lesson-steps.json"),
        evaluator_rubrics=_load_json(UNIT1_DIR / "evaluator-rubrics.json"),
        observation_form_mappings=_load_json(UNIT1_DIR / "observation-form-mappings.json"),
    )
