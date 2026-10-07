"""Ollama-backed assistant adapter.

Talks to a local Ollama server over ``/api/chat`` with ``stream: false`` and
turns the assistant's reply into validated dataclasses.

Two properties matter more than features here:

* **Nothing leaks out.** Transport failures, HTTP errors, and unparseable
  replies all surface as :class:`LlmUnavailableError` or
  :class:`LlmInvalidResponseError`, so callers never handle ``httpx`` types.
* **Nothing is invented.** ``format: "json"`` plus strict parsing means an
  unusable answer degrades into a recorded failure, never into wrong data.

The transport is ``httpx.AsyncClient``, so the client composes with other
async code and keeps every LLM call on one code path. Celery workers, however,
are synchronous, so :class:`OllamaClient` is a thin blocking facade that drives
the async client on a private event loop; Celery tasks use that facade. Health
checks go through the same path, so a ping and a real call fail identically.

Each call opens its own connection: a Celery task makes a single prompt, so
there is no session to keep alive, and a fresh connection cannot go stale
between two runs of the worker.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from apps.tasks.application.llm import (
    DailyPlanProposal,
    LlmInvalidResponseError,
    LlmUnavailableError,
    TaskDecomposition,
    TaskEvaluation,
    parse_daily_plan_proposal,
    parse_task_decomposition,
    parse_task_evaluation,
)
from apps.tasks.domain.value_objects import TaskId
from apps.tasks.infrastructure.prompts import (
    DECOMPOSER_SYSTEM_PROMPT,
    EVALUATOR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    build_decomposer_user_prompt,
    build_evaluator_user_prompt,
    build_planner_user_prompt,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3:8b"
DEFAULT_TIMEOUT_SECONDS = 120.0
HEALTH_TIMEOUT_SECONDS = 2.0
GENERATION_TEMPERATURE = 0.1
CODE_FENCE_PREFIXES = ("```json", "```")


@dataclass(frozen=True, slots=True)
class OllamaSettings:
    """Where the assistant lives and how it is addressed."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @property
    def chat_url(self) -> str:
        """Return the fully qualified chat endpoint."""
        return f"{self.base_url.rstrip('/')}/api/chat"

    @property
    def tags_url(self) -> str:
        """Return the endpoint used to probe availability."""
        return f"{self.base_url.rstrip('/')}/api/tags"


@dataclass(frozen=True, slots=True)
class AssistantAvailability:
    """Whether the assistant can be reached, and why not when it cannot."""

    available: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AsyncOllamaClient:
    """Awaitable assistant client used by every LLM code path."""

    settings: OllamaSettings = field(default_factory=OllamaSettings)
    transport: httpx.AsyncBaseTransport | None = None

    async def generate(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Return the JSON object the assistant produced for one prompt pair."""
        async with httpx.AsyncClient(
            timeout=self.settings.timeout_seconds,
            transport=self.transport,
        ) as client:
            content = await self._chat(client, system_prompt, user_prompt)
        return _decode_json_object(content)

    async def evaluate_task(
        self,
        *,
        name: str,
        description: str,
        due_date_iso: str | None,
    ) -> TaskEvaluation:
        """Return the assistant's assessment of one task."""
        payload = await self.generate(
            EVALUATOR_SYSTEM_PROMPT,
            build_evaluator_user_prompt(
                name=name,
                description=description,
                due_date_iso=due_date_iso,
            ),
        )
        return parse_task_evaluation(payload)

    async def decompose_task(
        self,
        *,
        name: str,
        description: str,
    ) -> TaskDecomposition:
        """Return the assistant's breakdown of one overwhelming task."""
        payload = await self.generate(
            DECOMPOSER_SYSTEM_PROMPT,
            build_decomposer_user_prompt(name=name, description=description),
        )
        return parse_task_decomposition(payload)

    async def plan_day(
        self,
        *,
        date_iso: str,
        max_hours: str,
        candidates: tuple[tuple[TaskId, str, str, str, str | None], ...],
    ) -> DailyPlanProposal:
        """Return the assistant's choice of tasks for one day."""
        payload = await self.generate(
            PLANNER_SYSTEM_PROMPT,
            build_planner_user_prompt(
                date_iso=date_iso,
                max_hours=max_hours,
                candidates=candidates,
            ),
        )
        return parse_daily_plan_proposal(payload, [row[0] for row in candidates])

    async def is_available(self) -> bool:
        """Return whether Ollama answers right now, never raising."""
        return (await self.probe()).available

    async def probe(self) -> AssistantAvailability:
        """Return availability plus a short, non-sensitive reason.

        The reason is a category, never the underlying exception text: an
        exception message embeds the daemon's host and port, which is
        infrastructure detail that has no business in an HTTP response.
        """
        try:
            async with httpx.AsyncClient(
                timeout=HEALTH_TIMEOUT_SECONDS,
                transport=self.transport,
            ) as client:
                response = await client.get(self.settings.tags_url)
        except httpx.ConnectError:
            logger.warning(
                "ollama health probe could not connect base_url=%s",
                self.settings.base_url,
            )
            return AssistantAvailability(False, "connection refused")
        except httpx.TimeoutException as error:
            logger.warning("ollama health probe timed out: %s", error)
            return AssistantAvailability(False, "timeout")
        except httpx.HTTPError as error:
            logger.warning("ollama health probe failed: %s", error)
            return AssistantAvailability(False, "transport error")
        if response.status_code == httpx.codes.OK:
            return AssistantAvailability(True, None)
        return AssistantAvailability(False, f"unexpected status {response.status_code}")

    async def _chat(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """POST one chat request and return the assistant's text content."""
        body = {
            "model": self.settings.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": GENERATION_TEMPERATURE},
        }
        try:
            response = await client.post(self.settings.chat_url, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            raise LlmUnavailableError(
                f"Ollama rejected the request with status {error.response.status_code}."
            ) from error
        except httpx.HTTPError as error:
            raise LlmUnavailableError(
                f"Ollama is unreachable at {self.settings.base_url}: {error}."
            ) from error
        except ValueError as error:
            raise LlmInvalidResponseError(
                "Ollama returned a body that is not JSON."
            ) from error
        return _extract_message_content(payload)


@dataclass(frozen=True, slots=True)
class OllamaClient:
    """Blocking facade over :class:`AsyncOllamaClient` for Celery workers.

    Celery's prefork pool is synchronous, so every task needs a blocking entry
    point. Each call runs a private event loop, which is safe here precisely
    because a worker process never has one already running; the async client
    stays the single place that knows how to talk HTTP.
    """

    settings: OllamaSettings = field(default_factory=OllamaSettings)
    transport: httpx.AsyncBaseTransport | None = None

    def _client(self) -> AsyncOllamaClient:
        return AsyncOllamaClient(settings=self.settings, transport=self.transport)

    def evaluate_task(
        self,
        *,
        name: str,
        description: str,
        due_date_iso: str | None,
    ) -> TaskEvaluation:
        """Return the assistant's assessment of one task."""
        return asyncio.run(
            self._client().evaluate_task(
                name=name,
                description=description,
                due_date_iso=due_date_iso,
            )
        )

    def decompose_task(
        self,
        *,
        name: str,
        description: str,
    ) -> TaskDecomposition:
        """Return the assistant's breakdown of one overwhelming task."""
        return asyncio.run(
            self._client().decompose_task(name=name, description=description)
        )

    def plan_day(
        self,
        *,
        date_iso: str,
        max_hours: str,
        candidates: tuple[tuple[TaskId, str, str, str, str | None], ...],
    ) -> DailyPlanProposal:
        """Return the assistant's choice of tasks for one day."""
        return asyncio.run(
            self._client().plan_day(
                date_iso=date_iso,
                max_hours=max_hours,
                candidates=candidates,
            )
        )

    def is_available(self) -> bool:
        """Return whether Ollama answers right now, never raising."""
        return asyncio.run(self._client().is_available())

    def probe(self) -> AssistantAvailability:
        """Return availability plus a short reason, never raising."""
        return asyncio.run(self._client().probe())


def settings_from_environment(
    base_url: str | None, model: str | None
) -> OllamaSettings:
    """Build settings from configuration, falling back to the local defaults.

    Values arrive already resolved from Django settings (or the environment)
    so this adapter never reads ``os.environ`` itself; it only decides what to
    do when a value is missing.
    """
    return OllamaSettings(
        base_url=base_url or DEFAULT_BASE_URL,
        model=model or DEFAULT_MODEL,
    )


def _decode_json_object(content: str) -> dict[str, Any]:
    """Parse ``content`` as a JSON object, tolerating a fenced code block."""
    try:
        payload = json.loads(_strip_code_fence(content))
    except (TypeError, ValueError) as error:
        raise LlmInvalidResponseError(
            "The assistant did not return valid JSON."
        ) from error
    if not isinstance(payload, dict):
        raise LlmInvalidResponseError("The assistant did not return a JSON object.")
    return payload


def _strip_code_fence(content: str) -> str:
    """Remove a surrounding code fence, which models add despite instructions."""
    if not isinstance(content, str):
        raise LlmInvalidResponseError("The assistant returned no text content.")
    stripped = content.strip()
    if not stripped.startswith(CODE_FENCE_PREFIXES):
        return stripped
    lines = stripped.splitlines()
    return "\n".join(lines[1:-1]).strip()


def _extract_message_content(payload: Any) -> str:
    """Return the assistant text from an Ollama chat response body."""
    if not isinstance(payload, dict):
        raise LlmInvalidResponseError("Ollama returned an unexpected response body.")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise LlmInvalidResponseError("Ollama response has no message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LlmInvalidResponseError("Ollama response has no message content.")
    return content
