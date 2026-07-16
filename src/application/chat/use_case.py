"""Chat use case — agentic tool-use loop yielding stream events."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
import json
from typing import cast

from structlog.stdlib import get_logger

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    TextDelta,
    ToolResultEvent,
    ToolStartEvent,
)
from src.application.chat.protocols import (
    LLMClientProtocol,
    LLMRequest,
    ToolContext,
    ToolExecutorFn,
)
from src.application.chat.user_data import strip_user_data, wrap_for_model
from src.config.settings import EffortLevel
from src.domain.entities.person import Person
from src.domain.exceptions import MaxRoundsExceededError, ResponseTruncatedError

logger = get_logger()

# Hard backstop on total client round-trips, as a multiple of max_turns.
# Sandbox-called rounds are cheap (cache reads, no context growth) but a
# runaway code loop must still terminate.
_SANDBOX_ROUNDS_PER_TURN = 5

type ChatEvent = (
    TextDelta
    | ToolStartEvent
    | ToolResultEvent
    | ServerToolStartEvent
    | ServerToolResultEvent
)


@dataclass(frozen=True, slots=True)
class ChatCommand:
    messages: list[dict[str, object]]
    system: list[dict[str, object]]
    tools: list[dict[str, object]]
    model_id: str
    max_turns: int
    max_tokens: int
    effort: EffortLevel
    current_user: Person
    persons: list[Person]


class ChatUseCase:
    def __init__(
        self, llm_client: LLMClientProtocol, tool_executor: ToolExecutorFn
    ) -> None:
        # The executor is injected (rather than imported from the registry)
        # so agentic tools can run this loop without an import cycle:
        # registry -> subagent -> use_case must never lead back to registry.
        self._llm = llm_client
        self._execute_tool = tool_executor

    async def execute(self, command: ChatCommand) -> AsyncGenerator[ChatEvent]:
        messages = list(command.messages)
        ctx = ToolContext(
            current_user=command.current_user,
            persons=command.persons,
            llm=self._llm,
        )
        # Sandbox container carried across turns of this loop — the API
        # requires it back when a sandbox-called tool's result is returned.
        container_id: str | None = None
        # Sandbox-called tools cost one client round-trip each but no model
        # context (results route back into the sandbox, prompt cache stays
        # warm), so a code loop over months would burn max_turns in one
        # analysis. Rounds whose tool calls all came from the sandbox count
        # against a larger budget instead of the model-turn budget
        # (live-verified: 6 months x 2 tools = 24 rounds in one question).
        model_turns = 0

        for round_index in range(command.max_turns * _SANDBOX_ROUNDS_PER_TURN):
            if model_turns >= command.max_turns:
                break
            request = LLMRequest(
                model=command.model_id,
                max_tokens=command.max_tokens,
                effort=command.effort,
                system=command.system,
                tools=command.tools,
                messages=messages,
                container=container_id,
            )
            async with self._llm.stream(request) as stream:
                async for event in stream:
                    if isinstance(
                        event,
                        TextDelta | ServerToolStartEvent | ServerToolResultEvent,
                    ):
                        yield event
                    else:
                        yield ToolStartEvent(name=event.name, tool_use_id=event.id)
                response = await stream.get_final_response()

            logger.info(
                "chat_turn",
                round=round_index,
                model_turns=model_turns,
                stop_reason=response.stop_reason,
            )
            container_id = response.container_id or container_id
            sandbox_only = bool(response.content) and all(
                tu.caller != "direct" for tu in response.content
            )
            if not sandbox_only:
                model_turns += 1

            if response.stop_reason == "pause_turn":
                # A paused turn carries no client tool_use blocks, so it must
                # be handled before the empty-content return below. Echo the
                # assistant turn back and re-request; the API resumes it.
                messages.append({
                    "role": "assistant",
                    "content": response.raw_content,
                })
                continue

            if response.stop_reason == "max_tokens":
                raise ResponseTruncatedError(
                    f"Response hit the {command.max_tokens}-token limit"
                )

            if response.stop_reason == "end_turn":
                return

            if not response.content:
                return

            tool_results: list[dict[str, object]] = []
            for tu in response.content:
                try:
                    summary = await self._execute_tool(tu.name, tu.input, ctx)
                    # The model boundary wraps UserData values in user_data
                    # tags; the event boundary strips any tag literals so the
                    # frontend always renders raw values.
                    yield ToolResultEvent(
                        name=tu.name,
                        tool_use_id=tu.id,
                        summary=cast(dict[str, object], strip_user_data(summary)),
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(wrap_for_model(summary)),
                    })
                except Exception as e:
                    # Error text may embed wrap()-tagged values — model
                    # content keeps them, the event summary must not.
                    error_summary = cast(
                        dict[str, object], strip_user_data({"error": str(e)})
                    )
                    yield ToolResultEvent(
                        name=tu.name,
                        tool_use_id=tu.id,
                        summary=error_summary,
                        is_error=True,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": str(e),
                        "is_error": True,
                    })

            messages.extend([
                {"role": "assistant", "content": response.raw_content},
                {"role": "user", "content": tool_results},
            ])

        raise MaxRoundsExceededError(f"Exceeded {command.max_turns} tool rounds")
