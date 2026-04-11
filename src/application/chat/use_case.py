"""Chat use case — agentic tool-use loop yielding stream events."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
import json

from structlog.stdlib import get_logger

from src.application.chat.events import TextDelta, ToolResultEvent, ToolStartEvent
from src.application.chat.protocols import LLMClientProtocol
from src.application.chat.tool_executor import execute_tool
from src.domain.entities.person import Person
from src.domain.exceptions import MaxRoundsExceededError

logger = get_logger()

type ChatEvent = TextDelta | ToolStartEvent | ToolResultEvent


@dataclass(frozen=True, slots=True)
class ChatCommand:
    messages: list[dict[str, object]]
    system: list[dict[str, object]]
    tools: list[dict[str, object]]
    model_id: str
    max_turns: int
    current_user: Person
    persons: list[Person]


class ChatUseCase:
    def __init__(self, llm_client: LLMClientProtocol) -> None:
        self._llm = llm_client

    async def execute(self, command: ChatCommand) -> AsyncGenerator[ChatEvent]:
        messages = list(command.messages)

        for turn in range(command.max_turns):
            async with self._llm.stream(
                model=command.model_id,
                max_tokens=8192,
                system=command.system,
                tools=command.tools,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if isinstance(event, TextDelta):
                        yield event
                    else:
                        yield ToolStartEvent(name=event.name, tool_use_id=event.id)
                response = await stream.get_final_response()

            logger.info(
                "chat_turn",
                turn=turn,
                stop_reason=response.stop_reason,
            )

            if response.stop_reason == "end_turn":
                return

            if not response.content:
                return

            tool_results: list[dict[str, object]] = []
            for tu in response.content:
                try:
                    summary = await execute_tool(
                        tu.name,
                        tu.input,
                        command.current_user,
                        command.persons,
                    )
                    yield ToolResultEvent(
                        name=tu.name, tool_use_id=tu.id, summary=summary
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(summary),
                    })
                except Exception as e:
                    error_summary: dict[str, object] = {"error": str(e)}
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
