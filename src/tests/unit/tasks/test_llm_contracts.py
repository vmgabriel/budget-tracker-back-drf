"""Tasks application-layer LLM contract tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.tasks.application.llm import (
    LlmInvalidResponseError,
    parse_daily_plan_proposal,
    parse_task_decomposition,
    parse_task_evaluation,
)
from apps.tasks.domain.value_objects import Duration, Priority, TaskId

pytestmark = pytest.mark.unit


def test_parses_a_complete_evaluation() -> None:
    evaluation = parse_task_evaluation(
        {
            "importance": "HIGH",
            "estimated_hours": 2.5,
            "suggested_goal": "Personal documents",
        }
    )

    assert evaluation.importance is Priority.HIGH
    assert evaluation.estimated_hours == Duration(Decimal("2.5"))
    assert evaluation.suggested_goal == "Personal documents"


def test_evaluation_accepts_a_null_suggested_goal() -> None:
    evaluation = parse_task_evaluation(
        {"importance": "low", "estimated_hours": 0.5, "suggested_goal": None}
    )

    assert evaluation.suggested_goal is None


def test_evaluation_accepts_integer_hours() -> None:
    evaluation = parse_task_evaluation(
        {"importance": "medium", "estimated_hours": 3, "suggested_goal": None}
    )

    assert evaluation.estimated_hours == Duration(Decimal("3"))


def test_evaluation_rejects_an_unknown_importance() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation(
            {"importance": "urgent", "estimated_hours": 1, "suggested_goal": None}
        )


def test_evaluation_rejects_a_missing_estimate() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation({"importance": "low", "suggested_goal": None})


def test_evaluation_rejects_negative_hours() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation(
            {"importance": "low", "estimated_hours": -1, "suggested_goal": None}
        )


def test_evaluation_rejects_hours_with_too_many_decimals() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation(
            {"importance": "low", "estimated_hours": 1.234, "suggested_goal": None}
        )


def test_evaluation_rejects_a_non_numeric_estimate() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation(
            {
                "importance": "low",
                "estimated_hours": "two hours",
                "suggested_goal": None,
            }
        )


def test_evaluation_rejects_a_boolean_estimate() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_evaluation(
            {"importance": "low", "estimated_hours": True, "suggested_goal": None}
        )


def test_parses_a_decomposition() -> None:
    decomposition = parse_task_decomposition(
        {
            "goal_name": "Kitchen renovation",
            "subtasks": [
                {"name": "Measure cabinets", "description": "", "estimated_hours": 2},
                {
                    "name": "Install cabinets",
                    "description": "Level them.",
                    "estimated_hours": 6.5,
                },
            ],
        }
    )

    assert decomposition.goal_name == "Kitchen renovation"
    assert [subtask.name for subtask in decomposition.subtasks] == [
        "Measure cabinets",
        "Install cabinets",
    ]
    assert decomposition.subtasks[1].estimated_hours == Duration(Decimal("6.5"))
    assert decomposition.subtasks[0].description == ""


def test_decomposition_rejects_an_empty_subtask_list() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_decomposition({"goal_name": "Kitchen", "subtasks": []})


def test_decomposition_rejects_a_malformed_subtask() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_decomposition(
            {
                "goal_name": "Kitchen",
                "subtasks": [{"name": "Install", "description": ""}],
            }
        )


def test_decomposition_rejects_a_nested_non_object_subtask() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_task_decomposition(
            {"goal_name": "Kitchen", "subtasks": ["install cabinets"]}
        )


def test_plan_proposal_keeps_the_backlog_order() -> None:
    first, second = TaskId(uuid4()), TaskId(uuid4())

    proposal = parse_daily_plan_proposal(
        {"task_ids": [str(second), str(first)], "total_hours": 3},
        [first, second],
    )

    assert proposal.task_ids == (second, first)


def test_plan_proposal_drops_hallucinated_ids() -> None:
    known = TaskId(uuid4())
    unknown = TaskId(uuid4())

    proposal = parse_daily_plan_proposal(
        {"task_ids": [str(known), str(unknown)], "total_hours": 2},
        [known],
    )

    assert proposal.task_ids == (known,)


def test_plan_proposal_rejects_a_malformed_id() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_daily_plan_proposal(
            {"task_ids": ["not-a-uuid"], "total_hours": 2},
            [TaskId(uuid4())],
        )


def test_plan_proposal_deduplicates_repeated_ids() -> None:
    task_id = TaskId(uuid4())

    proposal = parse_daily_plan_proposal(
        {"task_ids": [str(task_id), str(task_id)], "total_hours": 2},
        [task_id],
    )

    assert proposal.task_ids == (task_id,)


def test_plan_proposal_rejects_a_non_list_selection() -> None:
    with pytest.raises(LlmInvalidResponseError):
        parse_daily_plan_proposal(
            {"task_ids": str(TaskId(uuid4())), "total_hours": 2},
            [TaskId(uuid4())],
        )
