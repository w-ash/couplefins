"""Stop-reason handling and event flow in the agentic tool loop."""

import json
from unittest.mock import AsyncMock

import pytest

from src.application.chat.events import (
    ServerToolResultEvent,
    ServerToolStartEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from src.application.chat.protocols import LLMResponse, ToolContext, ToolUseBlock
from src.application.chat.use_case import ChatCommand, ChatEvent, ChatUseCase
from src.domain.exceptions import MaxRoundsExceededError, ResponseTruncatedError
from tests.fixtures.factories import make_person
from tests.fixtures.fake_llm_client import FakeLLMClient, FakeScript

_PAUSED_RAW_CONTENT: list[dict[str, object]] = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"}
]

# These scripts never emit tool_use blocks, so the executor must stay uncalled.
_unused_executor = AsyncMock(side_effect=AssertionError("unexpected tool call"))


def _pause_script() -> FakeScript:
    return FakeScript(
        response=LLMResponse(
            stop_reason="pause_turn",
            content=[],
            raw_content=_PAUSED_RAW_CONTENT,
        )
    )


def _command(fake_messages: list[dict[str, object]], max_turns: int) -> ChatCommand:
    alice = make_person(name="Alice")
    return ChatCommand(
        messages=fake_messages,
        system=[],
        tools=[],
        model_id="claude-opus-4-8",
        max_turns=max_turns,
        max_tokens=16384,
        effort="high",
        current_user=alice,
        persons=[alice],
    )


async def _drain(use_case: ChatUseCase, command: ChatCommand) -> list[ChatEvent]:
    return [event async for event in use_case.execute(command)]


class TestStopReasons:
    async def test_pause_turn_resumes_with_assistant_echo(self) -> None:
        fake = FakeLLMClient([_pause_script(), FakeScript()])
        original = [{"role": "user", "content": "hi"}]

        await _drain(
            ChatUseCase(fake, _unused_executor), _command(original, max_turns=3)
        )

        assert len(fake.captured_messages) == 2
        first, second = fake.captured_messages
        assert second == [
            *first,
            {"role": "assistant", "content": _PAUSED_RAW_CONTENT},
        ]

    async def test_pause_turn_is_bounded_by_max_turns(self) -> None:
        fake = FakeLLMClient([_pause_script(), _pause_script()])

        with pytest.raises(MaxRoundsExceededError):
            await _drain(
                ChatUseCase(fake, _unused_executor),
                _command([{"role": "user", "content": "hi"}], max_turns=2),
            )

    async def test_max_tokens_raises_truncation_error(self) -> None:
        fake = FakeLLMClient([
            FakeScript(
                response=LLMResponse(
                    stop_reason="max_tokens", content=[], raw_content=[]
                )
            )
        ])

        with pytest.raises(ResponseTruncatedError):
            await _drain(
                ChatUseCase(fake, _unused_executor),
                _command([{"role": "user", "content": "hi"}], max_turns=3),
            )


class TestToolRoundTrip:
    async def test_tool_use_executes_and_appends_result(self) -> None:
        """Pins the loop mechanics programmatic tool calling relies on: a
        tool_use block (direct or sandbox-originated — same shape) reaches
        the injected executor with a ToolContext, and its result goes back
        as a JSON tool_result on the next request."""
        tool_use = ToolUseBlock(id="toolu_1", name="get_tags", input={"limit": 5})
        raw = [{"type": "tool_use", "id": "toolu_1", "name": "get_tags"}]
        fake = FakeLLMClient([
            FakeScript(
                events=[tool_use],
                response=LLMResponse(
                    stop_reason="tool_use", content=[tool_use], raw_content=raw
                ),
            ),
            FakeScript(),
        ])
        executor = AsyncMock(return_value={"tags": ["shared"]})

        events = await _drain(
            ChatUseCase(fake, executor),
            _command([{"role": "user", "content": "hi"}], max_turns=3),
        )

        (call,) = executor.await_args_list
        name, tool_input, ctx = call.args
        assert (name, tool_input) == ("get_tags", {"limit": 5})
        assert isinstance(ctx, ToolContext)
        assert ctx.llm is fake
        assert ToolStartEvent(name="get_tags", tool_use_id="toolu_1") in events
        assert (
            ToolResultEvent(
                name="get_tags",
                tool_use_id="toolu_1",
                summary={"tags": ["shared"]},
            )
            in events
        )
        second_request = fake.captured_messages[1]
        assert second_request[-2] == {"role": "assistant", "content": raw}
        assert second_request[-1] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": json.dumps({"tags": ["shared"]}),
                }
            ],
        }


class TestContainerThreading:
    async def test_container_id_is_echoed_on_subsequent_turns(self) -> None:
        """Live-verified 400: once a turn ran in a sandbox container, the
        follow-up request (returning sandbox-called tool results) must carry
        that container id."""
        tool_use = ToolUseBlock(id="toolu_1", name="get_tags", input={})
        fake = FakeLLMClient([
            FakeScript(
                response=LLMResponse(
                    stop_reason="tool_use",
                    content=[tool_use],
                    raw_content=[{"type": "tool_use", "id": "toolu_1"}],
                    container_id="cont_1",
                )
            ),
            FakeScript(),
        ])
        executor = AsyncMock(return_value={})

        await _drain(
            ChatUseCase(fake, executor),
            _command([{"role": "user", "content": "hi"}], max_turns=3),
        )

        assert fake.captured_containers == [None, "cont_1"]


class TestSandboxRoundBudget:
    async def test_sandbox_called_rounds_do_not_consume_model_turns(self) -> None:
        """A code loop calling tools programmatically costs one round-trip
        per call; those rounds must not drain max_turns (live-verified: one
        6-month analysis burned 24 rounds)."""
        sandbox_call = ToolUseBlock(
            id="toolu_1",
            name="get_tags",
            input={},
            caller="code_execution_20260120",
        )
        sandbox_script = FakeScript(
            response=LLMResponse(
                stop_reason="tool_use",
                content=[sandbox_call],
                raw_content=[{"type": "tool_use", "id": "toolu_1"}],
            )
        )
        fake = FakeLLMClient([sandbox_script, sandbox_script, FakeScript()])
        executor = AsyncMock(return_value={})

        # max_turns=1 would fail immediately if sandbox rounds counted.
        await _drain(
            ChatUseCase(fake, executor),
            _command([{"role": "user", "content": "hi"}], max_turns=1),
        )

        assert executor.await_count == 2

    async def test_round_backstop_still_terminates(self) -> None:
        sandbox_call = ToolUseBlock(
            id="toolu_1",
            name="get_tags",
            input={},
            caller="code_execution_20260120",
        )
        endless = FakeScript(
            response=LLMResponse(
                stop_reason="tool_use",
                content=[sandbox_call],
                raw_content=[{"type": "tool_use", "id": "toolu_1"}],
            )
        )
        fake = FakeLLMClient([endless] * 10)
        executor = AsyncMock(return_value={})

        with pytest.raises(MaxRoundsExceededError):
            await _drain(
                ChatUseCase(fake, executor),
                _command([{"role": "user", "content": "hi"}], max_turns=1),
            )

        # max_turns * _SANDBOX_ROUNDS_PER_TURN = 5 rounds for max_turns=1.
        assert executor.await_count == 5


class TestServerToolEvents:
    async def test_server_tool_events_pass_through(self) -> None:
        start = ServerToolStartEvent(
            name="code_execution",
            tool_use_id="srvtoolu_1",
            input={"code": "print(1)"},
        )
        result = ServerToolResultEvent(
            tool_use_id="srvtoolu_1", stdout="1\n", stderr="", return_code=0
        )
        fake = FakeLLMClient([FakeScript(events=[start, result])])

        events = await _drain(
            ChatUseCase(fake, _unused_executor),
            _command([{"role": "user", "content": "hi"}], max_turns=2),
        )

        assert events == [start, result]
