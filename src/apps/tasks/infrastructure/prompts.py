"""Prompt text for the assistant.

Prompts are infrastructure, not domain: they describe how a particular model
must be spoken to, so they change when the model or the desired output shape
changes, and nothing else in the codebase should care.

Every prompt follows the same contract, because a small model follows contracts
much better than prose:

* state the task in one line, then the exact JSON shape, then the rules;
* give worked examples (few-shot), including the awkward cases;
* forbid prose before or after the JSON object;
* keep input delimited and truncated, so a long description cannot drown the
  instructions or let the task text impersonate them.

Users control this data, so each field is emitted as a JSON string literal via
:func:`json.dumps`: a description containing ``"output": {...}`` stays inert
text instead of becoming an instruction.
"""

import json
from collections.abc import Sequence

from apps.tasks.domain.value_objects import TaskId

# Truncation limits for the prompt surface. They are deliberately smaller than
# the domain storage limits (200 chars for a name, 5000 for a description): a
# long description is context the model must reason over, not context it needs.
MAX_NAME_PROMPT_LENGTH = 300
MAX_DESCRIPTION_PROMPT_LENGTH = 2000
MAX_CANDIDATES_IN_PROMPT = 60

MISSING_DESCRIPTION_PLACEHOLDER = "(no description provided)"


EVALUATOR_SYSTEM_PROMPT = """\
You are a task assessment engine for a personal productivity system.

Given one task, return how important it is and how many hours it realistically
takes.

Respond with a single JSON object and nothing else. No prose, no explanation, \
no markdown code fences.

Shape:
{
  "importance": "high" | "medium" | "low",
  "estimated_hours": <number>,
  "suggested_goal": <string or null>
}

Rules:
- "importance" must be exactly one of: high, medium, low.
- "estimated_hours" is a positive number with at most two decimals, expressed \
in hours of focused work for one person. It must be realistic for a single \
sitting, not the total across a project.
- "suggested_goal" is a short umbrella outcome (2 to 6 words) this task \
belongs to, or null when the task stands alone. Never invent a goal for \
trivial or unrelated chores.
- Output the object even when the input is vague or empty. Never refuse, never \
ask questions.

Examples:

Input:
{"name": "Renew passport", "description": "Expiring in two months", \
"due_date": "2026-03-01"}
Output:
{"importance": "high", "estimated_hours": 2.5, \
"suggested_goal": "Personal documents"}

Input:
{"name": "Water the plants", "description": "", "due_date": null}
Output:
{"importance": "low", "estimated_hours": 0.5, "suggested_goal": null}
"""


DECOMPOSER_SYSTEM_PROMPT = """\
You are a task decomposition engine for a personal productivity system.

Given one task that is too large to face at once, return the umbrella goal it \
belongs to and the ordered subtasks that make it manageable.

Respond with a single JSON object and nothing else. No prose, no explanation, \
no markdown code fences.

Shape:
{
  "goal_name": <string>,
  "subtasks": [
    {
      "name": <string>,
      "description": <string>,
      "estimated_hours": <number>
    }
  ]
}

Rules:
- Return between 2 and 6 subtasks, in execution order.
- "goal_name" is a short umbrella outcome (2 to 6 words), not a copy of the \
task name.
- Each "name" is a concrete action starting with a verb.
- Each "description" is one sentence of actionable detail; use "" when nothing \
needs saying.
- "estimated_hours" is a positive number with at most two decimals. No single \
subtask may exceed the original task's estimate.
- Subtasks must together cover the original task with no leftover step.
- Output the object even when the input is vague. Never refuse.

Example:

Input:
{"name": "Renovate the kitchen", "description": "Replace cabinets, install \
sink, repaint walls"}
Output:
{
  "goal_name": "Kitchen renovation",
  "subtasks": [
    {"name": "Measure and order cabinets", "description": "Measure wall \
sections and confirm layout with the supplier.", "estimated_hours": 2.0},
    {"name": "Install new cabinets", "description": "Remove old units and \
fit the new ones level.", "estimated_hours": 6.0},
    {"name": "Install sink and taps", "description": "", \
"estimated_hours": 2.5},
    {"name": "Prep and repaint walls", "description": "Patch, prime, then \
two coats.", "estimated_hours": 3.5}
  ]
}
"""


PLANNER_SYSTEM_PROMPT = """\
You are a daily planning engine for a personal productivity system.

Given the backlog of a single person's unfinished tasks and the hour budget for \
one day, choose which tasks to schedule today.

Respond with a single JSON object and nothing else. No prose, no explanation, \
no markdown code fences.

Shape:
{
  "task_ids": [<string>, ...],
  "total_hours": <number>
}

Rules:
- "task_ids" must contain only ids copied verbatim from the given backlog, in \
the order you recommend working on them. Never invent, shorten, or alter an id.
- The sum of the chosen tasks' "estimated_hours" must not exceed the daily \
budget. Omit any task that would push the day over budget.
- Prefer tasks that are high importance, or whose due_date is today or already \
passed, before low importance or distant deadlines.
- Do not select the same id twice, and do not return more ids than the budget \
can hold.
- An empty "task_ids" list is valid when nothing fits or nothing is worth \
doing.
- "total_hours" is the sum of the selected tasks' hours, with at most two \
decimals. It must be 0 when "task_ids" is empty.

Example:

Budget: 3.0 hours
Backlog:
[
  {"id": "11111111-1111-1111-1111-111111111111", "name": "File taxes", \
"importance": "high", "estimated_hours": 2.0, "due_date": "2026-02-01"},
  {"id": "22222222-2222-2222-2222-222222222222", "name": "Repaint hallway", \
"importance": "low", "estimated_hours": 5.0, "due_date": null}
]
Output:
{"task_ids": ["11111111-1111-1111-1111-111111111111"], "total_hours": 2.0}
"""


def build_evaluator_user_prompt(
    *,
    name: str,
    description: str,
    due_date_iso: str | None,
) -> str:
    """Return the user turn asking for one task to be assessed.

    Field order is fixed to match the examples in the system prompt, because a
    small model copies the shape it was shown.
    """
    return (
        "Assess this task.\n"
        f"name: {_literal(name, MAX_NAME_PROMPT_LENGTH)}\n"
        f"description: {_literal(description, MAX_DESCRIPTION_PROMPT_LENGTH)}\n"
        f"due_date: {_due_date_literal(due_date_iso)}"
    )


def build_decomposer_user_prompt(*, name: str, description: str) -> str:
    """Return the user turn asking for one task to be broken into subtasks."""
    return (
        "Break this task into subtasks.\n"
        f"name: {_literal(name, MAX_NAME_PROMPT_LENGTH)}\n"
        f"description: {_literal(description, MAX_DESCRIPTION_PROMPT_LENGTH)}"
    )


def build_planner_user_prompt(
    *,
    date_iso: str,
    max_hours: str,
    candidates: Sequence[tuple[TaskId, str, str, str, str | None]],
) -> str:
    """Return the user turn asking which backlog tasks fill one day.

    ``candidates`` is one tuple per task:
    ``(task_id, name, importance, estimated_hours, due_date_iso)``. The list is
    truncated to :data:`MAX_CANDIDATES_IN_PROMPT` because an unbounded backlog
    would exceed the context window, and the truncation is stated in the prompt
    so the assistant never assumes it saw everything.
    """
    rows = list(candidates)[:MAX_CANDIDATES_IN_PROMPT]
    backlog = json.dumps(
        [
            {
                "id": str(task_id),
                "name": name[:MAX_NAME_PROMPT_LENGTH],
                "importance": importance,
                "estimated_hours": hours,
                "due_date": due_date_iso,
            }
            for task_id, name, importance, hours, due_date_iso in rows
        ],
        ensure_ascii=False,
        indent=2,
    )
    omitted = len(candidates) - len(rows)
    omission_note = (
        f"\nNote: {omitted} further tasks were omitted for length; plan only "
        "from the tasks shown."
        if omitted > 0
        else ""
    )
    return (
        f"Plan the day for {_literal(date_iso, 32)}.\n"
        f"Daily budget in hours: {_literal(max_hours, 32)}\n"
        f"Backlog:\n{backlog}{omission_note}"
    )


def _literal(value: str | None, limit: int) -> str:
    """Return ``value`` as a quoted JSON string, truncated and never empty."""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return json.dumps(MISSING_DESCRIPTION_PLACEHOLDER)
    if len(text) > limit:
        text = text[:limit].rstrip()
    return json.dumps(text, ensure_ascii=False)


def _due_date_literal(due_date_iso: str | None) -> str:
    """Return a due date as a quoted literal, or ``null`` when there is none."""
    if due_date_iso is None:
        return "null"
    return _literal(due_date_iso, 32)
