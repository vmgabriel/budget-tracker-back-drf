"""Daily plan generation use case backed by the assistant port.

The assistant proposes which backlog tasks fill a day; this use case turns that
proposal into storage. Two safeguards make the proposal trustworthy enough to
act on automatically:

* only tasks the owner actually owns and still has in ``todo`` are offered, and
  the parser already dropped any invented identifier, so a hallucination cannot
  reach the schedule;
* the day's total hours are recomputed from the stored estimates rather than
  taken from the model's ``total_hours``. A model that miscounts is a cosmetic
  problem; a plan whose stored hours disagree with its own tasks is a lie the
  user sees every time they open the day.

A failed generation leaves the existing plan untouched: the owner's own
arrangement is never destroyed because a provider was down.
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import (
    DailyPlanDetails,
    daily_plan_details,
    ordered_tasks,
)
from apps.tasks.application.llm import DailyPlanProposal
from apps.tasks.application.ports.llm import LlmAssistant
from apps.tasks.application.ports.repositories import (
    DailyPlanRepository,
    TaskRepository,
)
from apps.tasks.domain.entities import DailyPlan, Task
from apps.tasks.domain.value_objects import TaskId, TaskStatus, UserId
from shared.domain.ports.clock import Clock

PLAN_GENERATED = "generated"
PLAN_ALREADY_FILLED = "already_filled"
PLAN_FAILED = "failed"
PLAN_EMPTY = "empty_backlog"


@dataclass(frozen=True, slots=True)
class DailyPlanGenerationOutcome:
    """What happened when a day was sent to the assistant to be planned."""

    status: str
    plan: DailyPlanDetails | None = None
    scheduled_task_ids: tuple[TaskId, ...] = ()

    @property
    def is_failure(self) -> bool:
        """Return whether the assistant could not be used."""
        return self.status == PLAN_FAILED


class GenerateDailyPlanWithLlm:
    """Fill one day of the owner's backlog with the assistant's selection."""

    def __init__(
        self,
        plans: DailyPlanRepository,
        tasks: TaskRepository,
        assistant: LlmAssistant,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._plans = plans
        self._tasks = tasks
        self._assistant = assistant
        self._clock = clock
        self._policy = policy

    def execute(self, user_id: UUID, day: date) -> DailyPlanGenerationOutcome:
        """Plan ``day`` from the owner's unfinished tasks.

        An existing day is replaced wholesale rather than appended to: a plan is
        one proposal for one day, and mixing a regenerated selection with tasks
        the owner scheduled by hand would produce a day nobody proposed.
        """
        backlog = [
            task
            for task in self._tasks.get_by_user_id(UserId(user_id))
            if task.status is TaskStatus.TODO and task.id is not None
        ]
        if not backlog:
            return DailyPlanGenerationOutcome(status=PLAN_EMPTY)

        try:
            proposal = self._assistant.plan_day(
                date_iso=day.isoformat(),
                max_hours=str(self._policy.daily_plan_max_hours.hours),
                candidates=tuple(
                    (
                        task.id,  # type: ignore[misc]
                        task.name,
                        task.importance.value,
                        str(task.estimated_hours.hours),
                        task.due_date.isoformat() if task.due_date else None,
                    )
                    for task in backlog
                ),
            )
        except Exception:
            return DailyPlanGenerationOutcome(status=PLAN_FAILED)

        return self._apply(UserId(user_id), day, backlog, proposal)

    def _apply(
        self,
        user_id: UserId,
        day: date,
        backlog: list[Task],
        proposal: DailyPlanProposal,
    ) -> DailyPlanGenerationOutcome:
        """Store the proposed day, recomputing its hours from real estimates."""
        by_id = {task.id: task for task in backlog if task.id is not None}
        selected = [by_id[task_id] for task_id in proposal.task_ids if task_id in by_id]
        if not selected:
            # The assistant chose nothing, which is a legitimate answer for a
            # day that cannot fit anything. Existing plans are left alone so a
            # poor answer never empties a day the owner had already arranged.
            return DailyPlanGenerationOutcome(status=PLAN_ALREADY_FILLED)

        plan = self._plans.get_by_user_and_date(user_id, day)
        if plan is None:
            plan = self._plans.save(
                DailyPlan.create(
                    user_id=user_id,
                    date=day,
                    now=self._clock.now(),
                    generated_by_llm=True,
                )
            )
        else:
            plan.clear_tasks()
            plan.mark_as_llm_generated()

        for task in selected:
            if task.id is None:
                continue
            plan.add_task(task.id, task.estimated_hours)
        saved = self._plans.update(plan)
        return DailyPlanGenerationOutcome(
            status=PLAN_GENERATED,
            plan=daily_plan_details(
                saved,
                ordered_tasks(saved, self._tasks.get_by_ids(saved.task_ids)),
                self._policy.overwhelmed_threshold,
                self._policy.daily_plan_max_hours,
            ),
            scheduled_task_ids=tuple(
                task_id for task_id in saved.task_ids if task_id is not None
            ),
        )


__all__ = (
    "PLAN_ALREADY_FILLED",
    "PLAN_EMPTY",
    "PLAN_FAILED",
    "PLAN_GENERATED",
    "DailyPlanGenerationOutcome",
    "GenerateDailyPlanWithLlm",
)
