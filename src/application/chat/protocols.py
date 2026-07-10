"""LLM client protocol — application-layer abstraction over any LLM provider."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Protocol

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    TextDelta,
)
from src.config.settings import EffortLevel
from src.domain.entities.person import Person


@dataclass(frozen=True, slots=True)
class ToolUseBlock:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    input: dict[str, object]
    # Who invoked the tool: "direct" (the model) or the code-execution tool
    # type when the sandbox called it programmatically.
    caller: str = "direct"


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Final response from a single LLM turn."""

    stop_reason: str
    content: list[ToolUseBlock]
    raw_content: list[dict[str, object]] = field(default_factory=list)
    # Sandbox container for this turn. Must be echoed on the next request of
    # the same loop — the API requires it when returning results for
    # sandbox-called tools (live-verified 400 without it).
    container_id: str | None = None


type LLMStreamEvent = (
    TextDelta | ToolUseBlock | ServerToolStartEvent | ServerToolResultEvent
)


class LLMStream(Protocol):
    """Async iterator over LLM stream events with access to the final response."""

    def __aiter__(self) -> AsyncIterator[LLMStreamEvent]: ...

    async def get_final_response(self) -> LLMResponse: ...


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """One LLM turn's inputs, bundled so the protocol surface stays stable."""

    model: str
    max_tokens: int
    effort: EffortLevel
    system: list[dict[str, object]]
    tools: list[dict[str, object]]
    messages: list[dict[str, object]]
    # Sandbox container to resume; required by the API when returning
    # results for sandbox-called tools.
    container: str | None = None


class LLMClientProtocol(Protocol):
    """Protocol for streaming LLM interactions."""

    def stream(self, request: LLMRequest) -> AbstractAsyncContextManager[LLMStream]: ...


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Everything a tool handler may need beyond its own input.

    Carries the LLM client so agentic tools (delegate_analysis) can run a
    sub-loop without the registry importing the use case — the context flows
    down from the loop that already owns the client.
    """

    current_user: Person
    persons: list[Person]
    llm: LLMClientProtocol


type ToolExecutorFn = Callable[
    [str, dict[str, object], ToolContext], Awaitable[dict[str, object]]
]
