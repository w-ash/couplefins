"""Research subagent: toolset isolation, summary return, truncation path."""

from unittest.mock import AsyncMock
import uuid

from src.application.chat.events import TextDelta
from src.application.chat.protocols import LLMResponse, ToolUseBlock
from src.application.chat.registry import (
    _SUBAGENT_HOT_TOOLS,
    build_subagent_tools,
    execute_tool,
)
from src.application.chat.subagent import run_subagent
from src.application.chat.use_case import ChatCommand, ChatUseCase
from src.application.chat.user_data import UserData
from src.config.settings import ChatConfig
from tests.fixtures.factories import make_person
from tests.fixtures.fake_llm_client import (
    FakeLLMClient,
    FakeScript,
    make_tool_context,
)

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
PERSONS = [ALICE, BOB]

_CFG = ChatConfig(subagent_max_turns=3, subagent_effort="low")


class TestSubagentToolset:
    def test_toolset_is_read_only(self) -> None:
        tool_list = build_subagent_tools()
        # Every dispatched tool is a read; the only server block is the
        # trailing tool-search tool (deferred reads need a way in).
        dispatched = {t["name"] for t in tool_list if "input_schema" in t}
        assert dispatched
        assert all(n.startswith(("get_", "search_")) for n in dispatched)
        names = {t["name"] for t in tool_list}
        assert "delegate_analysis" not in names
        assert "code_execution" not in names
        assert tool_list[-1] == {
            "type": "tool_search_tool_bm25_20251119",
            "name": "tool_search_tool_bm25",
        }

    def test_toolset_carries_no_allowed_callers(self) -> None:
        assert all("allowed_callers" not in t for t in build_subagent_tools())

    def test_hot_set_loads_up_front_everything_else_defers(self) -> None:
        tool_list = build_subagent_tools()
        loaded = {
            t["name"]
            for t in tool_list
            if "defer_loading" not in t and "input_schema" in t
        }
        assert loaded == set(_SUBAGENT_HOT_TOOLS)
        # Under the ~10-tool accuracy ceiling including the search block.
        assert len(loaded) + 1 <= 10
        deferred = {t["name"] for t in tool_list if t.get("defer_loading")}
        assert deferred, "the long tail must stay deferred"
        assert not deferred & set(_SUBAGENT_HOT_TOOLS)

    def test_cache_stamp_on_last_hot_tool(self) -> None:
        """The breakpoint sits on the last hot dispatched tool — never the
        trailing raw search block, which rejects cache_control."""
        tool_list = build_subagent_tools()
        stamped = [t for t in tool_list if "cache_control" in t]
        assert len(stamped) == 1
        assert stamped[0]["cache_control"] == {"type": "ephemeral"}
        assert "input_schema" in stamped[0]
        assert stamped[0]["name"] in _SUBAGENT_HOT_TOOLS
        hot_indices = [
            i
            for i, t in enumerate(tool_list)
            if "input_schema" in t and "defer_loading" not in t
        ]
        assert tool_list.index(stamped[0]) == hot_indices[-1]


class TestRunSubagent:
    async def test_returns_final_text_as_summary(self) -> None:
        tool_use = ToolUseBlock(id="toolu_1", name="get_tags", input={})
        fake = FakeLLMClient([
            FakeScript(
                events=[TextDelta(text="Checking tags first. "), tool_use],
                response=LLMResponse(
                    stop_reason="tool_use",
                    content=[tool_use],
                    raw_content=[{"type": "tool_use", "id": "toolu_1"}],
                ),
            ),
            FakeScript(events=[TextDelta(text="Found 3 anomalies.")]),
        ])
        executor = AsyncMock(return_value={"tags": []})
        ctx = make_tool_context(ALICE, PERSONS, llm=fake)

        result = await run_subagent(
            "find anomalies",
            None,
            ctx,
            tools=build_subagent_tools(),
            execute_fn=executor,
            cfg=_CFG,
        )

        # Narration before the tool call is process, not answer.
        assert result == {"summary": "Found 3 anomalies."}
        # Marked untrusted: the summary re-enters the write-capable main
        # model, so the model boundary must wrap it (v1.9.1).
        assert isinstance(result["summary"], UserData)
        assert executor.await_count == 1

    async def test_subagent_runs_with_own_settings_and_toolset(self) -> None:
        fake = FakeLLMClient([FakeScript(events=[TextDelta(text="ok")])])
        ctx = make_tool_context(ALICE, PERSONS, llm=fake)

        await run_subagent(
            "question",
            "2026 only",
            ctx,
            tools=build_subagent_tools(),
            execute_fn=AsyncMock(),
            cfg=_CFG,
        )

        (request,) = fake.captured_requests
        assert request.effort == "low"
        assert {t["name"] for t in request.tools} == {
            t["name"] for t in build_subagent_tools()
        }
        assert request.messages[0]["content"] == "question\n\nScope: 2026 only"
        system_text = str(request.system[0]["text"])
        assert "<untrusted_content>" in system_text
        assert "Alice, Bob" in system_text

    async def test_turn_limit_returns_truncation_prefix(self) -> None:
        tool_use = ToolUseBlock(id="toolu_1", name="get_tags", input={})
        looping = FakeScript(
            events=[TextDelta(text="digging... ")],
            response=LLMResponse(
                stop_reason="tool_use",
                content=[tool_use],
                raw_content=[{"type": "tool_use", "id": "toolu_1"}],
            ),
        )
        fake = FakeLLMClient([looping] * 20)
        ctx = make_tool_context(ALICE, PERSONS, llm=fake)

        result = await run_subagent(
            "audit everything",
            None,
            ctx,
            tools=build_subagent_tools(),
            execute_fn=AsyncMock(return_value={}),
            cfg=_CFG,
        )

        summary = result["summary"]
        assert isinstance(summary, UserData)  # truncation payload wrapped too
        assert summary.startswith("[Analysis truncated at turn limit")
        assert "digging..." in summary


class TestNestedIntegration:
    async def test_outer_loop_delegates_and_receives_summary(self) -> None:
        """Outer fake LLM calls delegate_analysis; the inner loop consumes
        the following scripts from the same client and its final text comes
        back as the outer tool_result."""
        delegate_call = ToolUseBlock(
            id="toolu_outer",
            name="delegate_analysis",
            input={"question": "find anomalies in 2026"},
        )
        fake = FakeLLMClient([
            FakeScript(
                response=LLMResponse(
                    stop_reason="tool_use",
                    content=[delegate_call],
                    raw_content=[{"type": "tool_use", "id": "toolu_outer"}],
                ),
            ),
            # Inner subagent turn:
            FakeScript(events=[TextDelta(text="Two duplicate rent charges.")]),
            # Outer loop resumes:
            FakeScript(events=[TextDelta(text="Here's what I found.")]),
        ])
        alice = make_person(name="Alice")
        command = ChatCommand(
            messages=[{"role": "user", "content": "audit our year"}],
            system=[],
            tools=[],
            model_id="claude-opus-4-8",
            max_turns=4,
            max_tokens=16384,
            effort="high",
            current_user=alice,
            persons=[alice],
        )

        events = [e async for e in ChatUseCase(fake, execute_tool).execute(command)]

        summaries = [
            e.summary
            for e in events
            if hasattr(e, "summary") and e.name == "delegate_analysis"
        ]
        # The SSE-facing event summary is stripped raw text …
        assert summaries == [{"summary": "Two duplicate rent charges."}]
        assert "<user_data>" not in str(summaries[0]["summary"])
        # … while the model-facing tool_result carries the wrapped summary.
        resumed_messages = fake.captured_messages[-1]
        tool_result_content = str(resumed_messages[-1]["content"])
        assert (
            "<user_data>Two duplicate rent charges.</user_data>" in tool_result_content
        )
