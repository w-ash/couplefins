"""Stop-reason handling in the agentic tool loop."""

import pytest

from src.application.chat.protocols import LLMResponse
from src.application.chat.use_case import ChatCommand, ChatEvent, ChatUseCase
from src.domain.exceptions import MaxRoundsExceededError, ResponseTruncatedError
from tests.fixtures.factories import make_person
from tests.fixtures.fake_llm_client import FakeLLMClient, FakeScript

_PAUSED_RAW_CONTENT: list[dict[str, object]] = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"}
]


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

        await _drain(ChatUseCase(fake), _command(original, max_turns=3))

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
                ChatUseCase(fake),
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
                ChatUseCase(fake),
                _command([{"role": "user", "content": "hi"}], max_turns=3),
            )
