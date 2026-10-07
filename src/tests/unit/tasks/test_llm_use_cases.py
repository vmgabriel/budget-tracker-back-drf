"""Unit tests for the assistant-backed tasks use cases."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.tasks.application.config import PlanningPolicy
from apps.tasks.application.llm import (
    DailyPlanProposal,
    LlmInvalidResponseError,
    LlmUnavailableError,
    SubtaskProposal,
    TaskDecomposition,
    TaskEvaluation,
)
from apps.tasks.application.use_cases import (
    DecomposeOverwhelmingTask,
    EvaluateTaskWithLlm,
    GenerateDailyPlanWithLlm,
)
from apps.tasks.domain.entities import Task
from apps.tasks.domain.value_objects import (
    Duration,
    OverwhelmedThreshold,
    Priority,
    TaskId,
    TaskStatus,
    UserId,
)
from tests.unit.tasks.fakes import (
    FIXED_NOW,
    FakeClock,
    FakeDailyPlanRepository,
    FakeGoalRepository,
    FakeLlmAssistant,
    FakeTaskRepository,
)

pytestmark = pytest.mark.unit

OWNER_ID = uuid4()
DAY = date(2026, 1, 15)
OVERWHELMING_HOURS = Duration(Decimal("8"))
SMALL_HOURS = Duration(Decimal("1.5"))


def _policy() -> PlanningPolicy:
    return PlanningPolicy(
        overwhelmed_threshold=OverwhelmedThreshold(Decimal("4")),
        daily_plan_max_hours=Duration(Decimal("8")),
    )


def _evaluation(
    importance: Priority = Priority.HIGH,
    hours: Duration = SMALL_HOURS,
) -> TaskEvaluation:
    return TaskEvaluation(
        importance=importance,
        estimated_hours=hours,
        suggested_goal=None,
    )


def _stored_task(
    repository: FakeTaskRepository,
    *,
    hours: Duration = SMALL_HOURS,
    name: str = "Renew passport",
    description: str = "Expiring soon",
    due_date: date | None = DAY,
    checked: bool = False,
) -> UUID:
    """Persist a task and return the raw UUID the use cases take."""
    task = repository.save(
        Task.create(
            user_id=UserId(OWNER_ID),
            name=name,
            description=description,
            importance=Priority.MEDIUM,
            estimated_hours=hours,
            due_date=due_date,
            now=FIXED_NOW,
        )
    )
    task.is_checked_by_llm = checked
    if task.id is None:
        raise AssertionError("A saved task must have an identity.")
    return task.id.value


# --- evaluation -------------------------------------------------------------


def test_evaluation_applies_importance_and_effort() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks)
    assistant = FakeLlmAssistant(evaluation=_evaluation())

    outcome = EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(
        task_id
    )

    stored = tasks.get_by_id(TaskId(task_id))
    assert outcome.status == "applied"
    assert stored is not None
    assert stored.importance is Priority.HIGH
    assert stored.estimated_hours == SMALL_HOURS
    assert stored.is_checked_by_llm is True
    assert stored.llm_evaluation_failed is False


def test_evaluation_sends_the_due_date_as_an_iso_string() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks, due_date=date(2026, 3, 1))
    assistant = FakeLlmAssistant(evaluation=_evaluation())

    EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(task_id)

    assert assistant.evaluate_calls[0]["due_date_iso"] == "2026-03-01"


def test_evaluation_reports_no_due_date_as_none() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks, due_date=None)
    assistant = FakeLlmAssistant(evaluation=_evaluation())

    EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(task_id)

    assert assistant.evaluate_calls[0]["due_date_iso"] is None


def test_evaluation_skips_an_already_checked_task() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks, checked=True)
    assistant = FakeLlmAssistant(evaluation=_evaluation())

    outcome = EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(
        task_id
    )

    assert outcome.status == "already_checked"
    assert assistant.evaluate_calls == []


def test_forced_evaluation_rechecks_an_already_checked_task() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks, checked=True)
    assistant = FakeLlmAssistant(evaluation=_evaluation(Priority.LOW))

    outcome = EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(
        task_id, force=True
    )

    stored = tasks.get_by_id(TaskId(task_id))
    assert outcome.status == "applied"
    assert stored is not None
    assert stored.importance is Priority.LOW


def test_evaluation_reports_a_missing_task() -> None:
    outcome = EvaluateTaskWithLlm(
        FakeTaskRepository(), FakeLlmAssistant(), FakeClock(), _policy()
    ).execute(uuid4())

    assert outcome.status == "not_found"


@pytest.mark.parametrize(
    "failure",
    [
        LlmUnavailableError("connection refused"),
        LlmInvalidResponseError("not JSON"),
        RuntimeError("provider bug outside the port vocabulary"),
    ],
    ids=["unavailable", "invalid-response", "unexpected"],
)
def test_evaluation_degrades_on_any_assistant_failure(failure: Exception) -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks)
    assistant = FakeLlmAssistant(failure=failure)

    outcome = EvaluateTaskWithLlm(tasks, assistant, FakeClock(), _policy()).execute(
        task_id
    )

    stored = tasks.get_by_id(TaskId(task_id))
    assert outcome.status == "failed"
    assert outcome.is_failure is True
    assert stored is not None
    # Only the failure flag moves: a broken assistant must not be able to
    # overwrite the effort estimate the owner entered.
    assert stored.llm_evaluation_failed is True
    assert stored.is_checked_by_llm is False
    assert stored.importance is Priority.MEDIUM
    assert stored.estimated_hours == SMALL_HOURS


def test_a_later_success_clears_an_earlier_failure() -> None:
    tasks = FakeTaskRepository()
    task_id = _stored_task(tasks)
    use_case = EvaluateTaskWithLlm(
        tasks,
        FakeLlmAssistant(failure=LlmUnavailableError("down")),
        FakeClock(),
        _policy(),
    )
    use_case.execute(task_id)

    recovered = EvaluateTaskWithLlm(
        tasks, FakeLlmAssistant(evaluation=_evaluation()), FakeClock(), _policy()
    )
    recovered.execute(task_id, force=True)

    stored = tasks.get_by_id(TaskId(task_id))
    assert stored is not None
    assert stored.llm_evaluation_failed is False
    assert stored.is_checked_by_llm is True


# --- decomposition ----------------------------------------------------------


def _decomposition() -> TaskDecomposition:
    return TaskDecomposition(
        goal_name="Kitchen renovation",
        subtasks=(
            SubtaskProposal("Measure cabinets", "", Duration(Decimal("2"))),
            SubtaskProposal("Install cabinets", "Level them.", Duration(Decimal("3"))),
        ),
    )


def test_decomposition_creates_a_goal_with_the_proposed_subtasks() -> None:
    tasks = FakeTaskRepository()
    goals = FakeGoalRepository()
    task_id = _stored_task(tasks, hours=OVERWHELMING_HOURS)
    assistant = FakeLlmAssistant(decomposition=_decomposition())

    outcome = DecomposeOverwhelmingTask(
        tasks, goals, assistant, FakeClock(), _policy()
    ).execute(task_id)

    assert outcome.status == "applied"
    assert outcome.goal is not None
    stored = goals.get_by_id(outcome.goal.id)
    assert stored is not None
    assert stored.name == "Kitchen renovation"
    assert [subtask.name for subtask in outcome.subtasks] == [
        "Measure cabinets",
        "Install cabinets",
    ]
    assert all(subtask.goal_id == stored.id for subtask in outcome.subtasks)


def test_decomposition_closes_the_original_task_without_deleting_it() -> None:
    tasks = FakeTaskRepository()
    goals = FakeGoalRepository()
    task_id = _stored_task(tasks, hours=OVERWHELMING_HOURS)

    DecomposeOverwhelmingTask(
        tasks,
        goals,
        FakeLlmAssistant(decomposition=_decomposition()),
        FakeClock(),
        _policy(),
    ).execute(task_id)

    original = tasks.get_by_id(TaskId(task_id))
    assert original is not None
    assert original.status is TaskStatus.DONE
    # Kept rather than deleted so a poor suggestion stays recoverable.
    assert "Renew passport" in {task.name for task in tasks.tasks.values()}


def test_decomposition_subtasks_inherit_the_deadline_and_start_low() -> None:
    tasks = FakeTaskRepository()
    goals = FakeGoalRepository()
    task_id = _stored_task(tasks, hours=OVERWHELMING_HOURS, due_date=date(2026, 4, 1))

    outcome = DecomposeOverwhelmingTask(
        tasks,
        goals,
        FakeLlmAssistant(decomposition=_decomposition()),
        FakeClock(),
        _policy(),
    ).execute(task_id)

    for subtask in outcome.subtasks:
        assert subtask.due_date == date(2026, 4, 1)
        # The assistant ranked the parent, not its steps.
        assert subtask.importance is Priority.LOW


def test_decomposition_skips_a_task_that_already_fits_in_a_day() -> None:
    tasks = FakeTaskRepository()
    goals = FakeGoalRepository()
    task_id = _stored_task(tasks, hours=SMALL_HOURS)
    assistant = FakeLlmAssistant(decomposition=_decomposition())

    outcome = DecomposeOverwhelmingTask(
        tasks, goals, assistant, FakeClock(), _policy()
    ).execute(task_id)

    assert outcome.status == "not_overwhelming"
    assert assistant.decompose_calls == []
    assert goals.goals == {}


def test_decomposition_degrades_and_writes_nothing_on_failure() -> None:
    tasks = FakeTaskRepository()
    goals = FakeGoalRepository()
    task_id = _stored_task(tasks, hours=OVERWHELMING_HOURS)

    outcome = DecomposeOverwhelmingTask(
        tasks,
        goals,
        FakeLlmAssistant(failure=LlmUnavailableError("down")),
        FakeClock(),
        _policy(),
    ).execute(task_id)

    stored = tasks.get_by_id(TaskId(task_id))
    assert outcome.status == "failed"
    assert outcome.is_failure is True
    assert goals.goals == {}
    assert stored is not None
    assert stored.llm_evaluation_failed is True
    assert stored.status is TaskStatus.TODO


def test_decomposition_reports_a_missing_task() -> None:
    outcome = DecomposeOverwhelmingTask(
        FakeTaskRepository(),
        FakeGoalRepository(),
        FakeLlmAssistant(),
        FakeClock(),
        _policy(),
    ).execute(uuid4())

    assert outcome.status == "not_found"


# --- daily plan -------------------------------------------------------------


def _backlog_task(
    repository: FakeTaskRepository,
    *,
    name: str,
    hours: Duration,
    status: TaskStatus = TaskStatus.TODO,
) -> UUID:
    task = repository.save(
        Task.create(
            user_id=UserId(OWNER_ID),
            name=name,
            description="",
            importance=Priority.HIGH,
            estimated_hours=hours,
            status=status,
            now=FIXED_NOW,
        )
    )
    if task.id is None:
        raise AssertionError("A saved task must have an identity.")
    return task.id.value


def test_plan_offers_only_unfinished_tasks() -> None:
    tasks = FakeTaskRepository()
    todo = _backlog_task(tasks, name="File taxes", hours=SMALL_HOURS)
    _backlog_task(tasks, name="Finished", hours=SMALL_HOURS, status=TaskStatus.DONE)
    assistant = FakeLlmAssistant(
        plan=DailyPlanProposal((TaskId(todo),), Duration(Decimal("1.5")))
    )

    GenerateDailyPlanWithLlm(
        FakeDailyPlanRepository(), tasks, assistant, FakeClock(), _policy()
    ).execute(OWNER_ID, DAY)

    offered = {row[0] for row in assistant.plan_calls[0]["candidates"]}
    assert offered == {TaskId(todo)}


def test_plan_sends_the_budget_and_the_day_to_the_assistant() -> None:
    tasks = FakeTaskRepository()
    todo = _backlog_task(tasks, name="File taxes", hours=SMALL_HOURS)
    assistant = FakeLlmAssistant(
        plan=DailyPlanProposal((TaskId(todo),), Duration(Decimal("1.5")))
    )

    GenerateDailyPlanWithLlm(
        FakeDailyPlanRepository(), tasks, assistant, FakeClock(), _policy()
    ).execute(OWNER_ID, DAY)

    call = assistant.plan_calls[0]
    assert call["date_iso"] == DAY.isoformat()
    assert call["max_hours"] == "8"


def test_plan_creates_the_day_and_marks_it_as_generated() -> None:
    tasks = FakeTaskRepository()
    plans = FakeDailyPlanRepository()
    todo = _backlog_task(tasks, name="File taxes", hours=Duration(Decimal("2")))

    outcome = GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(
            plan=DailyPlanProposal((TaskId(todo),), Duration(Decimal("999")))
        ),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    stored = plans.get_by_user_and_date(UserId(OWNER_ID), DAY)
    assert outcome.status == "generated"
    assert stored is not None
    assert stored.generated_by_llm is True
    assert stored.task_ids == [TaskId(todo)]
    # Recomputed from the stored estimate, not taken from the model's claim.
    assert stored.total_hours == Duration(Decimal("2"))


def test_plan_replaces_an_existing_generated_day() -> None:
    tasks = FakeTaskRepository()
    plans = FakeDailyPlanRepository()
    first = _backlog_task(tasks, name="File taxes", hours=Duration(Decimal("2")))
    second = _backlog_task(tasks, name="Call dentist", hours=Duration(Decimal("1")))

    GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(
            plan=DailyPlanProposal((TaskId(first),), Duration(Decimal("2")))
        ),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(
            plan=DailyPlanProposal((TaskId(second),), Duration(Decimal("1")))
        ),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    stored = plans.get_by_user_and_date(UserId(OWNER_ID), DAY)
    assert stored is not None
    assert stored.task_ids == [TaskId(second)]
    assert stored.total_hours == Duration(Decimal("1"))


def test_plan_ignores_a_hallucinated_task_id() -> None:
    tasks = FakeTaskRepository()
    plans = FakeDailyPlanRepository()
    todo = _backlog_task(tasks, name="File taxes", hours=Duration(Decimal("2")))
    invented = TaskId(uuid4())

    GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(
            plan=DailyPlanProposal((TaskId(todo), invented), Duration(Decimal("2")))
        ),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    stored = plans.get_by_user_and_date(UserId(OWNER_ID), DAY)
    assert stored is not None
    assert stored.task_ids == [TaskId(todo)]


def test_plan_leaves_an_existing_day_alone_when_nothing_was_selected() -> None:
    tasks = FakeTaskRepository()
    plans = FakeDailyPlanRepository()
    todo = _backlog_task(tasks, name="File taxes", hours=Duration(Decimal("2")))

    GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(
            plan=DailyPlanProposal((TaskId(todo),), Duration(Decimal("2")))
        ),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    outcome = GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(plan=DailyPlanProposal((), Duration(Decimal("0")))),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    stored = plans.get_by_user_and_date(UserId(OWNER_ID), DAY)
    assert outcome.status == "already_filled"
    # A poor answer must never empty a day the owner had already arranged.
    assert stored is not None
    assert stored.task_ids == [TaskId(todo)]


def test_plan_does_nothing_for_an_empty_backlog() -> None:
    assistant = FakeLlmAssistant()

    outcome = GenerateDailyPlanWithLlm(
        FakeDailyPlanRepository(),
        FakeTaskRepository(),
        assistant,
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    assert outcome.status == "empty_backlog"
    assert assistant.plan_calls == []


def test_plan_degrades_and_touches_nothing_on_failure() -> None:
    tasks = FakeTaskRepository()
    plans = FakeDailyPlanRepository()
    _backlog_task(tasks, name="File taxes", hours=Duration(Decimal("2")))

    outcome = GenerateDailyPlanWithLlm(
        plans,
        tasks,
        FakeLlmAssistant(failure=LlmUnavailableError("down")),
        FakeClock(),
        _policy(),
    ).execute(OWNER_ID, DAY)

    assert outcome.status == "failed"
    assert outcome.is_failure is True
    assert plans.get_by_user_and_date(UserId(OWNER_ID), DAY) is None
