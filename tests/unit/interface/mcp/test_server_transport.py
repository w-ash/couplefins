"""End-to-end transport: a real MCP ClientSession over in-memory streams.

Stands up the couplefins server and drives it through the SDK's own client,
so handler wiring, annotation serialisation, and the injected
confirm/confirm_token fields are exercised over the actual JSON-RPC
protocol — not just called in-process. DB-backed pieces are stubbed:
``_resolve_context`` (person lookup) and ``execute_tool`` /
``execute_confirmed_action``; the write propose path is the real, DB-free
one.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import json
import uuid

import anyio
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
import pytest

from src.application.chat import tool_executor
from src.application.chat.pending_actions import PendingAction, PendingActionStore
from src.application.chat.protocols import ToolContext
from src.interface.mcp import confirmation, server
from tests.fixtures.factories import make_person
from tests.fixtures.fake_llm_client import make_tool_context

ALICE = make_person(name="Alice", id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
BOB = make_person(name="Bob", id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))


@pytest.fixture(autouse=True)
def fake_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve the acting person without a DB."""

    async def _fake_resolve(person_name: str) -> ToolContext:
        return make_tool_context(ALICE, [ALICE, BOB])

    monkeypatch.setattr(server, "_resolve_context", _fake_resolve)


@asynccontextmanager
async def _connected_client() -> AsyncIterator[ClientSession]:
    """Yield an initialised client session wired to the couplefins server."""
    built = server.build_server("Alice")
    async with create_client_server_memory_streams() as (
        client_streams,
        server_streams,
    ):
        client_read, client_write = client_streams
        server_read, server_write = server_streams
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                lambda: built.run(
                    server_read, server_write, built.create_initialization_options()
                )
            )
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session
            tg.cancel_scope.cancel()


def _text(result: object) -> dict[str, object]:
    """Parse the single text block of a CallToolResult back to JSON."""
    content = result.content
    parsed = json.loads(content[0].text)
    assert isinstance(parsed, dict)
    return parsed


class TestListTools:
    async def test_lists_exposed_tools_only(self) -> None:
        async with _connected_client() as session:
            listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        assert names == {s.name for s in server.exposed_specs()}
        for hidden in ("code_execution", "delegate_analysis", "tool_search_tool_bm25"):
            assert hidden not in names

    async def test_annotations_and_confirm_fields_ride_the_wire(self) -> None:
        async with _connected_client() as session:
            listed = await session.list_tools()
        by_name = {t.name: t for t in listed.tools}
        read = by_name["search_transactions"]
        write = by_name["record_settlement"]
        assert read.annotations is not None
        assert read.annotations.read_only_hint is True
        assert write.annotations is not None
        assert write.annotations.destructive_hint is True
        assert "confirm" in write.input_schema.get("properties", {})
        assert "confirm_token" in write.input_schema.get("properties", {})


class TestCallTool:
    async def test_read_call_dispatches_and_returns_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _fake_execute(
            name: str, args: dict[str, object], ctx: ToolContext
        ) -> dict[str, object]:
            return {"tool": name, "ok": True}

        monkeypatch.setattr(server, "execute_tool", _fake_execute)
        async with _connected_client() as session:
            result = await session.call_tool("search_transactions", {})
        assert _text(result) == {"tool": "search_transactions", "ok": True}

    async def test_user_data_tags_stripped_from_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Handlers wrap user-originated strings in <user_data> tags as a
        # chat-side prompt-injection defense. MCP clients are untaught, so
        # the tags must not reach them — stripped before the wire.
        async def _fake_execute(
            name: str, args: dict[str, object], ctx: ToolContext
        ) -> dict[str, object]:
            return {"merchant": "<user_data>Whole Foods</user_data>", "ok": True}

        monkeypatch.setattr(server, "execute_tool", _fake_execute)
        async with _connected_client() as session:
            result = await session.call_tool("search_transactions", {})
        raw = result.content[0].text
        assert "<user_data>" not in raw
        assert "</user_data>" not in raw
        assert _text(result) == {"merchant": "Whole Foods", "ok": True}

    async def test_unknown_tool_returns_error_result(self) -> None:
        async with _connected_client() as session:
            result = await session.call_tool("does_not_exist", {})
        assert result.is_error
        assert "Unknown tool" in str(_text(result)["error"])

    async def test_agentic_tool_not_callable(self) -> None:
        async with _connected_client() as session:
            result = await session.call_tool("delegate_analysis", {"question": "x"})
        assert result.is_error
        assert "Unknown tool" in str(_text(result)["error"])

    async def test_write_two_phase_over_the_wire(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fresh = PendingActionStore()
        monkeypatch.setattr(confirmation, "pending_action_store", fresh)
        monkeypatch.setattr(tool_executor, "pending_action_store", fresh)

        async def _fake_commit(
            action: PendingAction, current_user: object
        ) -> tuple[dict[str, object], str | None]:
            return {"status": "confirmed", "description": "done"}, "settlements"

        monkeypatch.setattr(confirmation, "execute_confirmed_action", _fake_commit)

        args: dict[str, object] = {
            "from_person": "Alice",
            "to_person": "Bob",
            "amount": 50.0,
        }
        async with _connected_client() as session:
            preview = _text(await session.call_tool("record_settlement", dict(args)))
            assert preview["status"] == "needs_confirmation"

            committed = _text(
                await session.call_tool(
                    "record_settlement",
                    {
                        **args,
                        "confirm": True,
                        "confirm_token": preview["confirm_token"],
                    },
                )
            )
        assert committed["status"] == "confirmed"
