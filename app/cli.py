from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.content_loader import load_unit1_content
from app.runtime.diagnostics import diagnose_event, summarize_learner, validate_evidence_event
from app.runtime.learner_record import (
    merge_session_into_learner_record,
    store_active_session,
    submit_observation_to_learner_record,
)
from app.runtime.session_orchestrator import resume_or_plan_session
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
from app.validation.validate_content import main as validate_content_main


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _dump_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal CLI for Unit 1 content and diagnosis.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate-content", help="Validate app content files.")

    diagnose_parser = subparsers.add_parser("diagnose", help="Diagnose one evidence input JSON file.")
    diagnose_parser.add_argument("--input", required=True, help="Path to the evidence event JSON file.")

    summarize_parser = subparsers.add_parser("summarize-learner", help="Summarize multiple evidence events for one learner.")
    summarize_parser.add_argument("--input", required=True, help="Path to a JSON array of evidence events.")

    start_session_parser = subparsers.add_parser("start-session", help="Create session state from one recommendation JSON object.")
    start_session_parser.add_argument("--input", required=True, help="Path to a recommendation JSON file.")

    advance_session_parser = subparsers.add_parser("advance-session", help="Advance session state by completing the current lesson step.")
    advance_session_parser.add_argument("--input", required=True, help="Path to a session state JSON file.")
    advance_session_parser.add_argument("--complete-step", required=True, help="Lesson step id to mark complete.")

    evaluate_parser = subparsers.add_parser("evaluate-step", help="Evaluate the current session step from learner response input.")
    evaluate_parser.add_argument("--session", required=True, help="Path to a session state JSON file.")
    evaluate_parser.add_argument("--input", required=True, help="Path to a step evaluation input JSON file.")
    evaluate_parser.add_argument("--apply", action="store_true", help="Apply completed decisions and auto-advance the session.")

    evaluate_form_parser = subparsers.add_parser("evaluate-form", help="Evaluate the current session step from an observation form input.")
    evaluate_form_parser.add_argument("--session", required=True, help="Path to a session state JSON file.")
    evaluate_form_parser.add_argument("--input", required=True, help="Path to an observation form JSON file.")
    evaluate_form_parser.add_argument("--apply", action="store_true", help="Apply completed decisions and auto-advance the session.")

    submit_observation_parser = subparsers.add_parser("submit-observation", help="Append an observation record, evaluate it, and update session state.")
    submit_observation_parser.add_argument("--session", required=True, help="Path to a session state JSON file.")
    submit_observation_parser.add_argument("--input", required=True, help="Path to an observation form JSON file.")

    submit_observation_record_parser = subparsers.add_parser(
        "submit-observation-to-learner-record",
        help="Submit an observation against learner_record.activeSession and refresh learner-level state.",
    )
    submit_observation_record_parser.add_argument("--learner", required=True, help="Path to a learner record JSON file.")
    submit_observation_record_parser.add_argument("--input", required=True, help="Path to an observation form JSON file.")
    submit_observation_record_parser.add_argument("--write", action="store_true", help="Write the updated learner record back to the learner file.")

    session_summary_parser = subparsers.add_parser("summarize-session-history", help="Convert session history to learner evidence and summarize it.")
    session_summary_parser.add_argument("--session", required=True, help="Path to a session state JSON file.")

    update_learner_parser = subparsers.add_parser("update-learner-record", help="Merge a session state into a learner record.")
    update_learner_parser.add_argument("--learner", required=True, help="Path to a learner record JSON file.")
    update_learner_parser.add_argument("--session", required=True, help="Path to a session state JSON file.")
    update_learner_parser.add_argument("--write", action="store_true", help="Write the updated learner record back to the learner file.")

    plan_session_parser = subparsers.add_parser("plan-next-session", help="Choose the next recommended session from a learner record.")
    plan_session_parser.add_argument("--learner", required=True, help="Path to a learner record JSON file.")

    resume_or_plan_parser = subparsers.add_parser(
        "resume-or-plan",
        help="Resume an in-progress session when possible, otherwise plan the next session.",
    )
    resume_or_plan_parser.add_argument("--learner", required=True, help="Path to a learner record JSON file.")

    sync_active_session_parser = subparsers.add_parser(
        "sync-active-session",
        help="Run resume-or-plan and store the resulting live session on the learner record.",
    )
    sync_active_session_parser.add_argument("--learner", required=True, help="Path to a learner record JSON file.")
    sync_active_session_parser.add_argument("--write", action="store_true", help="Write the updated learner record back to the learner file.")

    subparsers.add_parser("run-harness", help="Run the first Unit 1 harness.")
    return parser


def run_diagnose(input_path: Path) -> int:
    event = _load_json(input_path)
    errors = validate_evidence_event(event)
    if errors:
        print("Evidence validation failed:")
        for message in errors:
            print(f"- {message}")
        return 1

    content = load_unit1_content()
    result = diagnose_event(content, event)
    payload = {
        "mastery": result.mastery,
        "recommendations": result.recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_harness() -> int:
    from app.harness.run_harness import main as harness_main

    return harness_main()


def run_start_session(input_path: Path) -> int:
    recommendation = _load_json(input_path)
    try:
        session_state = create_session_state(recommendation)
    except ValueError as exc:
        print(f"Session start failed: {exc}")
        return 1

    print(json.dumps(session_state, ensure_ascii=False, indent=2))
    return 0


def run_advance_session(input_path: Path, completed_step: str) -> int:
    session_state = _load_json(input_path)
    try:
        updated_state = advance_session_state(session_state, completed_step)
    except ValueError as exc:
        print(f"Session advance failed: {exc}")
        return 1

    print(json.dumps(updated_state, ensure_ascii=False, indent=2))
    return 0


def run_evaluate_step(session_path: Path, input_path: Path, apply_result: bool) -> int:
    session_state = _load_json(session_path)
    evaluation_input = _load_json(input_path)
    content = load_unit1_content()
    try:
        evaluation_result = evaluate_current_step(session_state, evaluation_input, content.evaluator_rubrics)
        payload = evaluation_result if not apply_result else apply_evaluator_decision(session_state, evaluation_result)
    except ValueError as exc:
        print(f"Step evaluation failed: {exc}")
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_evaluate_form(session_path: Path, input_path: Path, apply_result: bool) -> int:
    session_state = _load_json(session_path)
    observation_form = _load_json(input_path)
    content = load_unit1_content()
    try:
        evaluation_input = observation_form_to_evaluation_input(session_state, observation_form, content.observation_form_mappings)
        evaluation_result = evaluate_current_step(session_state, evaluation_input, content.evaluator_rubrics)
        payload = evaluation_result if not apply_result else apply_evaluator_decision(session_state, evaluation_result)
    except ValueError as exc:
        print(f"Observation-form evaluation failed: {exc}")
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_submit_observation(session_path: Path, input_path: Path) -> int:
    session_state = _load_json(session_path)
    observation_form = _load_json(input_path)
    content = load_unit1_content()
    try:
        updated_state = submit_observation(
            session_state,
            observation_form,
            content.evaluator_rubrics,
            content.observation_form_mappings,
        )
    except ValueError as exc:
        print(f"Observation submission failed: {exc}")
        return 1

    print(json.dumps(updated_state, ensure_ascii=False, indent=2))
    return 0


def run_submit_observation_to_learner_record(learner_path: Path, input_path: Path, write_result: bool) -> int:
    learner_record = _load_json(learner_path)
    observation_form = _load_json(input_path)
    content = load_unit1_content()
    try:
        updated_record = submit_observation_to_learner_record(learner_record, observation_form, content)
    except ValueError as exc:
        print(f"Learner-record observation submission failed: {exc}")
        return 1

    if write_result:
        _dump_json(learner_path, updated_record)

    print(json.dumps(updated_record, ensure_ascii=False, indent=2))
    return 0


def run_summarize_session_history(session_path: Path) -> int:
    session_state = _load_json(session_path)
    content = load_unit1_content()
    try:
        events = session_history_to_evidence_events(session_state)
        result = summarize_learner(content, events)
    except ValueError as exc:
        print(f"Session-history summary failed: {exc}")
        return 1

    payload = {
        "learnerId": result.learnerId,
        "events": events,
        "skillSummaries": result.skillSummaries,
        "recommendations": result.recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def run_update_learner_record(learner_path: Path, session_path: Path, write_result: bool) -> int:
    learner_record = _load_json(learner_path)
    session_state = _load_json(session_path)
    content = load_unit1_content()
    try:
        updated_record = merge_session_into_learner_record(learner_record, session_state, content)
    except ValueError as exc:
        print(f"Learner record update failed: {exc}")
        return 1

    if write_result:
        _dump_json(learner_path, updated_record)

    print(json.dumps(updated_record, ensure_ascii=False, indent=2))
    return 0


def run_plan_next_session(learner_path: Path) -> int:
    learner_record = _load_json(learner_path)
    try:
        planned = plan_next_session(learner_record)
    except ValueError as exc:
        print(f"Next-session planning failed: {exc}")
        return 1

    print(json.dumps(planned, ensure_ascii=False, indent=2))
    return 0


def run_resume_or_plan(learner_path: Path) -> int:
    learner_record = _load_json(learner_path)
    try:
        result = resume_or_plan_session(learner_record)
    except ValueError as exc:
        print(f"Resume-or-plan failed: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_sync_active_session(learner_path: Path, write_result: bool) -> int:
    learner_record = _load_json(learner_path)
    try:
        orchestration_result = resume_or_plan_session(learner_record)
        updated_record = store_active_session(learner_record, orchestration_result)
    except ValueError as exc:
        print(f"Sync-active-session failed: {exc}")
        return 1

    if write_result:
        _dump_json(learner_path, updated_record)

    print(json.dumps(updated_record, ensure_ascii=False, indent=2))
    return 0


def run_summarize_learner(input_path: Path) -> int:
    events = _load_json(input_path)
    if not isinstance(events, list):
        print("Learner summary input must be a JSON array of evidence events.")
        return 1

    content = load_unit1_content()
    try:
        result = summarize_learner(content, events)
    except ValueError as exc:
        print(f"Learner summary failed: {exc}")
        return 1

    payload = {
        "learnerId": result.learnerId,
        "skillSummaries": result.skillSummaries,
        "recommendations": result.recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "validate-content":
        return validate_content_main()
    if args.command == "diagnose":
        return run_diagnose(Path(args.input))
    if args.command == "summarize-learner":
        return run_summarize_learner(Path(args.input))
    if args.command == "start-session":
        return run_start_session(Path(args.input))
    if args.command == "advance-session":
        return run_advance_session(Path(args.input), args.complete_step)
    if args.command == "evaluate-step":
        return run_evaluate_step(Path(args.session), Path(args.input), args.apply)
    if args.command == "evaluate-form":
        return run_evaluate_form(Path(args.session), Path(args.input), args.apply)
    if args.command == "submit-observation":
        return run_submit_observation(Path(args.session), Path(args.input))
    if args.command == "submit-observation-to-learner-record":
        return run_submit_observation_to_learner_record(Path(args.learner), Path(args.input), args.write)
    if args.command == "summarize-session-history":
        return run_summarize_session_history(Path(args.session))
    if args.command == "update-learner-record":
        return run_update_learner_record(Path(args.learner), Path(args.session), args.write)
    if args.command == "plan-next-session":
        return run_plan_next_session(Path(args.learner))
    if args.command == "resume-or-plan":
        return run_resume_or_plan(Path(args.learner))
    if args.command == "sync-active-session":
        return run_sync_active_session(Path(args.learner), args.write)
    if args.command == "run-harness":
        return run_harness()

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
