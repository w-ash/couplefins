"""Fake LLM client for chat integration tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from src.application.chat.events import TextDelta
from src.application.chat.protocols import LLMResponse, ToolUseBlock


@dataclass(frozen=True, slots=True)
class FakeScript:
    """One turn's scripted response from the fake LLM."""

    events: list[TextDelta | ToolUseBlock] = field(default_factory=list)
    response: LLMResponse = field(
        default_factory=lambda: LLMResponse(
            stop_reason="end_turn", content=[], raw_content=[]
        )
    )


class _FakeStream:
    def __init__(self, script: FakeScript) -> None:
        self._script = script

    def __aiter__(self) -> AsyncIterator[TextDelta | ToolUseBlock]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[TextDelta | ToolUseBlock]:
        for event in self._script.events:
            yield event

    async def get_final_response(self) -> LLMResponse:
        return self._script.response


class FakeLLMClient:
    """Implements LLMClientProtocol with scripted responses.

    Each call to stream() pops the next script. If scripts run out,
    returns a default end_turn response.
    """

    def __init__(self, scripts: list[FakeScript] | None = None) -> None:
        self._scripts = list(scripts or [])
        self.captured_system: list[dict[str, object]] | None = None

    @asynccontextmanager
    async def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict[str, object]],
        tools: list[dict[str, object]],
        messages: list[dict[str, object]],
    ) -> AsyncIterator[_FakeStream]:
        self.captured_system = system
        script = self._scripts.pop(0) if self._scripts else FakeScript()
        yield _FakeStream(script)
