"""Integration tests for the chat endpoint."""

import asyncio
import json

from httpx import AsyncClient

from src.application.chat.events import TextDelta
from src.application.chat.protocols import LLMResponse, ToolUseBlock
from src.domain.exceptions import ChatUnavailableError
from src.interface.api.dependencies import get_llm_client
from tests.fixtures.fake_llm_client import FakeLLMClient, FakeScript
from tests.integration.conftest import setup_and_login, upload_csv

_SIMPLE_CSV = """Date,Merchant,Category,Account,Original Statement,Notes,Amount,Tags
2026-03-01,Grocery Store,Groceries,Checking,,,-50.00,shared
2026-03-02,Electric Co,Utilities,Checking,,,-120.00,shared
"""


def _get_app(client: AsyncClient) -> object:
    return client._transport.app  # type: ignore[reportAttributeAccessIssue]


def _override_llm(client: AsyncClient, fake: FakeLLMClient) -> None:
    app = _get_app(client)
    app.dependency_overrides[get_llm_client] = lambda: fake  # type: ignore[reportAttributeAccessIssue]


def _clear_llm_override(client: AsyncClient) -> None:
    app = _get_app(client)
    app.dependency_overrides.pop(get_llm_client, None)  # type: ignore[reportAttributeAccessIssue]


def _parse_sse_events(text: str) -> list[dict[str, object]]:
    """Parse SSE 'data: {...}' lines into dicts."""
    events: list[dict[str, object]] = []
    for raw_line in text.strip().split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("data: "):
            events.append(json.loads(stripped[6:]))
    return events


def _text_only_script(text: str = "Hello!") -> FakeScript:
    return FakeScript(
        events=[TextDelta(text=text)],
        response=LLMResponse(
            stop_reason="end_turn",
            content=[],
            raw_content=[{"type": "text", "text": text}],
        ),
    )


def _tool_use_script(
    tool_name: str, tool_input: dict[str, object], tool_id: str = "tu_1"
) -> FakeScript:
    """Script where the LLM requests a tool call."""
    return FakeScript(
        events=[ToolUseBlock(id=tool_id, name=tool_name, input=tool_input)],
        response=LLMResponse(
            stop_reason="tool_use",
            content=[ToolUseBlock(id=tool_id, name=tool_name, input=tool_input)],
            raw_content=[
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": tool_input,
                }
            ],
        ),
    )


async def _post_chat(
    client: AsyncClient,
    cookies: dict[str, str],
    fake: FakeLLMClient,
    messages: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Post to /chat with a fake LLM client and return parsed SSE events."""
    _override_llm(client, fake)
    try:
        if messages is None:
            messages = [{"role": "user", "content": "Hello"}]
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": messages},
            auth=cookies,
        )
        assert resp.status_code == 200
        return _parse_sse_events(resp.text)
    finally:
        _clear_llm_override(client)


# --- Test 1: Text-only response ---


async def test_text_only_response(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script("Here is the answer.")])

    events = await _post_chat(client, cookies, fake)

    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) >= 1
    assert token_events[0]["text"] == "Here is the answer."

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


# --- Test 2: Single tool_use → real execution ---


async def test_single_tool_use(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, _SIMPLE_CSV, auth=cookies)

    fake = FakeLLMClient([
        _tool_use_script("get_settlement_balance", {"year": 2026, "month": 3}),
        _text_only_script("The balance is settled."),
    ])

    events = await _post_chat(client, cookies, fake)

    tool_starts = [e for e in events if e["type"] == "tool_start"]
    assert len(tool_starts) == 1
    assert tool_starts[0]["name"] == "get_settlement_balance"

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["name"] == "get_settlement_balance"
    assert tool_results[0]["is_error"] is False

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


# --- Test 2b: v1.8.1 read tool end-to-end against real uploaded data ---


async def test_read_parity_tool_upload_history(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, _SIMPLE_CSV, auth=cookies)

    fake = FakeLLMClient([
        _tool_use_script("get_upload_history", {}),
        _text_only_script("One upload so far."),
    ])

    events = await _post_chat(client, cookies, fake)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["is_error"] is False
    summary = tool_results[0]["summary"]
    assert summary["total_count"] == 1
    upload = summary["uploads"][0]
    assert upload["transaction_count"] == 2
    # Filenames are user-originated — wrapped for the model only. The SSE
    # summary the frontend receives must carry no tags...
    assert "<user_data>" not in json.dumps(summary)
    # ...while the model-facing tool_result content on the follow-up
    # request carries the wrapped filename.
    follow_up = fake.captured_messages[1][-1]
    model_content = json.dumps(follow_up)
    assert "<user_data>" in model_content


# --- Test 3: Parallel tool_use ---


async def test_parallel_tool_use(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, _SIMPLE_CSV, auth=cookies)

    tu1 = ToolUseBlock(
        id="tu_a",
        name="get_settlement_balance",
        input={"year": 2026, "month": 3},
    )
    tu2 = ToolUseBlock(
        id="tu_b", name="get_dashboard_status", input={"year": 2026, "month": 3}
    )
    parallel_script = FakeScript(
        events=[tu1, tu2],
        response=LLMResponse(
            stop_reason="tool_use",
            content=[tu1, tu2],
            raw_content=[
                {
                    "type": "tool_use",
                    "id": "tu_a",
                    "name": tu1.name,
                    "input": tu1.input,
                },
                {
                    "type": "tool_use",
                    "id": "tu_b",
                    "name": tu2.name,
                    "input": tu2.input,
                },
            ],
        ),
    )
    fake = FakeLLMClient([parallel_script, _text_only_script("Done.")])

    events = await _post_chat(client, cookies, fake)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 2
    assert all(r["is_error"] is False for r in tool_results)
    result_names = {e["name"] for e in tool_results}
    assert result_names == {"get_settlement_balance", "get_dashboard_status"}


# --- Test: client_date drives "today" in the system prompt ---


async def test_client_date_used_in_system_prompt(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script("Hi there.")])
    _override_llm(client, fake)
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "What's today's date?"}],
                "client_date": "2026-12-31",
            },
            auth=cookies,
        )
        assert resp.status_code == 200
    finally:
        _clear_llm_override(client)

    assert fake.captured_system is not None
    system_text = fake.captured_system[0]["text"]
    assert "Today is 2026-12-31" in system_text


async def test_missing_client_date_falls_back_to_server_date(
    client: AsyncClient,
) -> None:
    """No client_date sent (headless caller) — the route must not error and
    should fall back to a real calendar date rather than leaving "today"
    unresolved."""
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script("Hi there.")])
    _override_llm(client, fake)
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            auth=cookies,
        )
        assert resp.status_code == 200
    finally:
        _clear_llm_override(client)

    assert fake.captured_system is not None
    system_text = fake.captured_system[0]["text"]
    assert "Today is 20" in system_text  # any real 20xx calendar date


async def test_effort_override_reaches_llm_request(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script()])
    _override_llm(client, fake)
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "effort": "low",
            },
            auth=cookies,
        )
        assert resp.status_code == 200
    finally:
        _clear_llm_override(client)

    assert fake.captured_requests[0].effort == "low"


async def test_effort_defaults_to_config(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script()])

    await _post_chat(client, cookies, fake)

    assert fake.captured_requests[0].effort == "high"


async def test_invalid_effort_rejected(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    _override_llm(client, FakeLLMClient([_text_only_script()]))
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "effort": "turbo",
            },
            auth=cookies,
        )
    finally:
        _clear_llm_override(client)

    assert resp.status_code == 422


# --- Test 4: Unauthenticated → 401 ---


async def test_unauthenticated(client: AsyncClient) -> None:
    await setup_and_login(client)
    _override_llm(client, FakeLLMClient())
    try:
        # Clear cookie jar so the request is truly unauthenticated
        client.cookies.clear()
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        assert resp.status_code == 401
    finally:
        _clear_llm_override(client)


# --- Test 5: Missing API key → 503 ---


async def test_missing_api_key(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    def _raise_unavailable() -> None:
        raise ChatUnavailableError("Chat is not available")

    app = _get_app(client)
    app.dependency_overrides[get_llm_client] = _raise_unavailable  # type: ignore[reportAttributeAccessIssue]
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            auth=cookies,
        )
        assert resp.status_code == 503
    finally:
        _clear_llm_override(client)


# --- Test 6: Tool execution error → is_error in stream ---


async def test_tool_execution_error(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)

    fake = FakeLLMClient([
        _tool_use_script("search_transactions", {"bad_param": True}),
        _text_only_script("Sorry, that failed."),
    ])

    events = await _post_chat(client, cookies, fake)

    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["is_error"] is True

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


# --- Test 7: Max rounds exceeded ---


async def test_max_rounds_exceeded(client: AsyncClient) -> None:
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, _SIMPLE_CSV, auth=cookies)

    infinite_tool = _tool_use_script(
        "get_settlement_balance", {"year": 2026, "month": 3}
    )
    fake = FakeLLMClient([infinite_tool] * 20)

    from src.config.settings import get_settings

    settings = get_settings()
    original_max = settings.chat.max_turns
    settings.chat.max_turns = 2
    try:
        events = await _post_chat(client, cookies, fake)
    finally:
        settings.chat.max_turns = original_max

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["code"] == "MAX_ROUNDS_EXCEEDED"


# --- Test 7b: max_tokens truncation → RESPONSE_TRUNCATED error ---


async def test_max_tokens_truncation(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    truncated = FakeScript(
        events=[TextDelta(text="Half an ans")],
        response=LLMResponse(stop_reason="max_tokens", content=[], raw_content=[]),
    )
    fake = FakeLLMClient([truncated])

    events = await _post_chat(client, cookies, fake)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["code"] == "RESPONSE_TRUNCATED"


# --- Test 8: Client disconnect → clean cancellation ---


async def test_client_disconnect(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient([_text_only_script("Hello!")])
    _override_llm(client, fake)

    try:
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            auth=cookies,
        ) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    break
    finally:
        _clear_llm_override(client)

    # No assertion needed — test passes if no unhandled exception
    await asyncio.sleep(0.05)


# --- Test: Input size enforcement ---


async def test_message_too_large(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    _override_llm(client, FakeLLMClient())
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "x" * 25_000}]},
            auth=cookies,
        )
        assert resp.status_code == 422
    finally:
        _clear_llm_override(client)


async def test_total_content_too_large(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    messages = [{"role": "user", "content": "x" * 20_000} for _ in range(6)]
    _override_llm(client, FakeLLMClient())
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={"messages": messages},
            auth=cookies,
        )
        assert resp.status_code == 422
    finally:
        _clear_llm_override(client)


# --- Test: Rate limiting ---


async def test_rate_limit(client: AsyncClient) -> None:
    _, cookies = await setup_and_login(client)
    fake = FakeLLMClient()
    _override_llm(client, fake)

    from src.interface.api.routes.chat import _chat_limiter

    _chat_limiter.reset()

    try:
        for i in range(20):
            resp = await client.post(
                "/api/v1/chat",
                json={"messages": [{"role": "user", "content": f"msg {i}"}]},
                auth=cookies,
            )
            assert resp.status_code == 200, f"Request {i} failed: {resp.status_code}"

        resp = await client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "one too many"}]},
            auth=cookies,
        )
        assert resp.status_code == 429
    finally:
        _chat_limiter.reset()
        _clear_llm_override(client)


# --- v1.8.2: end-to-end propose → confirm flow for a write tool ---


async def test_finalize_period_propose_confirm_flow(client: AsyncClient) -> None:
    """The two-phase mutation contract end-to-end: the tool call proposes,
    the period stays open until the user confirms, and confirming locks it
    identically to the UI path."""
    persons, cookies = await setup_and_login(client)
    alice_id = persons[0]["id"]
    await upload_csv(client, alice_id, _SIMPLE_CSV, auth=cookies)

    # Turn 1: the model proposes finalizing March.
    fake = FakeLLMClient([
        _tool_use_script("finalize_period", {"year": 2026, "month": 3}),
        _text_only_script("Confirm to lock March."),
    ])
    events = await _post_chat(
        client,
        cookies,
        fake,
        messages=[{"role": "user", "content": "Lock March please"}],
    )
    tool_results = [e for e in events if e["type"] == "tool_result"]
    assert tool_results[0]["is_error"] is False
    summary = tool_results[0]["summary"]
    assert summary["status"] == "pending_confirmation"
    action_id = summary["action_id"]

    # Nothing applied yet — the proposal alone must not lock the month.
    status = await client.get(
        "/api/v1/reconciliation/period-status",
        params={"year": 2026, "month": 3},
        auth=cookies,
    )
    assert status.json()["is_finalized"] is False

    # Turn 2: the user confirms via the confirmation card.
    fake2 = FakeLLMClient([_text_only_script("March is locked.")])
    _override_llm(client, fake2)
    try:
        resp = await client.post(
            "/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": "Lock March please"}],
                "confirmation": {"action_id": action_id, "approved": True},
            },
            auth=cookies,
        )
        assert resp.status_code == 200
    finally:
        _clear_llm_override(client)

    status = await client.get(
        "/api/v1/reconciliation/period-status",
        params={"year": 2026, "month": 3},
        auth=cookies,
    )
    assert status.json()["is_finalized"] is True
