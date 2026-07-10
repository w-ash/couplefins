"""LLM client protocol — application-layer abstraction over any LLM provider."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Protocol

from src.application.chat.events import TextDelta
from src.config.settings import EffortLevel
from src.domain.entities.person import Person


@dataclass(frozen=True, slots=True)
class ToolUseBlock:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    input: dict[str, object]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Final response from a single LLM turn."""

    stop_reason: str
    content: list[ToolUseBlock]
    raw_content: list[dict[str, object]] = field(default_factory=list)


class LLMStream(Protocol):
    """Async iterator over LLM stream events with access to the final response."""

    def __aiter__(self) -> AsyncIterator[TextDelta | ToolUseBlock]: ...

    async def get_final_response(self) -> LLMResponse: ...


class LLMClientProtocol(Protocol):
    """Protocol for streaming LLM interactions."""

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        effort: EffortLevel,
        system: list[dict[str, object]],
        tools: list[dict[str, object]],
        messages: list[dict[str, object]],
    ) -> AbstractAsyncContextManager[LLMStream]: ...


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
