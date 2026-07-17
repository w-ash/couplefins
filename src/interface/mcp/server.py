"""Low-level MCP server built from the shared tool registry.

Verified against ``mcp==2.0.0b1`` / ``mcp-types==2.0.0b1`` (v2, stateless
core), the same pin mixd's server was live-verified on. RE-VERIFY on the
2026-07-28 stable-v2 bump — the low-level API below is beta:

- Types live in the separate ``mcp_types`` package (v2 removed
  ``mcp.types``): ``Tool``, ``ToolAnnotations``, ``TextContent``,
  ``CallToolResult``, ``ListToolsResult``, ``CallToolRequestParams``,
  ``PaginatedRequestParams``. ``Tool(input_schema=…)`` serialises to the
  ``inputSchema`` wire key; annotation fields serialise via alias.
- ``mcp.server.lowlevel.Server`` registers handlers via
  ``add_request_handler(method, params_type, handler)`` where the handler
  is ``async (ServerRequestContext, params) -> BaseModel | dict | None``.
- ``mcp.server.stdio.stdio_server()`` yields ``(read, write)`` streams;
  ``Server.run(...)`` owns the initialize handshake. stdout is the JSON-RPC
  channel — logging goes to stderr (``setup_stderr_logging``).

The low-level ``Server`` (not the high-level ``MCPServer``) is deliberate:
couplefins' tools are data — a ``REGISTRY`` tuple carrying hand-built JSON
schemas — whereas ``MCPServer.add_tool(fn)`` infers a schema from a Python
function. Iterating the registry into ``list_tools``/``call_tool`` is the
faithful fit.

Identity: the acting person comes from the ``COUPLEFINS_MCP_PERSON`` env
var (a person name), resolved against the DB through a short-TTL cache —
couplefins' ``ToolContext`` carries a full ``Person`` plus the persons
list, not a bare id. Resolution failures surface as actionable tool errors.
"""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
import json
import time
from typing import Final, cast

import anyio
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp_types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from structlog.stdlib import get_logger

from src.application.chat.protocols import (
    LLMRequest,
    LLMStream,
    ToolContext,
)
from src.application.chat.registry import REGISTRY, ToolSpec, execute_tool
from src.application.chat.tool_executor import resolve_person
from src.application.chat.user_data import strip_user_data
from src.application.runner import execute_use_case
from src.application.use_cases.list_persons import list_persons
from src.domain.entities.person import Person
from src.domain.exceptions import DomainError, ToolExecutionError
from src.interface.mcp.confirmation import (
    CONFIRM_FIELD,
    CONFIRM_TOKEN_FIELD,
    handle_write_call,
)
from src.interface.mcp.exposure import mcp_exposure
from src.interface.mcp.install import ENV_PERSON

logger = get_logger()

SERVER_NAME = "couplefins"

# Optional properties injected into every exposed write tool's schema so a
# client can drive the two-phase confirmation in-band. The base schemas set
# additionalProperties: false, so these must be declared as real properties.
_CONFIRM_PROPERTIES: dict[str, object] = {
    CONFIRM_FIELD: {
        "type": "boolean",
        "description": (
            "Omit (or false) to preview the change and receive a confirm_token. "
            "Set true — with the confirm_token from that preview and the same "
            "arguments — to commit."
        ),
    },
    CONFIRM_TOKEN_FIELD: {
        "type": "string",
        "description": "The confirm_token returned by a prior preview call.",
    },
}


class _UnavailableLLM:
    """LLMClientProtocol stand-in — agentic tools are not exposed over MCP.

    ``ToolContext`` requires an LLM client so chat's delegate_analysis can
    run a sub-loop; no MCP-exposed tool ever touches it. If one somehow
    does, fail loudly instead of making silent API calls.
    """

    def stream(self, request: LLMRequest) -> AbstractAsyncContextManager[LLMStream]:
        raise ToolExecutionError("Agentic tools are not available over MCP")


def mcp_annotations(spec: ToolSpec) -> ToolAnnotations:
    """Derive MCP tool annotations from the registry ``kind``.

    Fixed formula (annotations are untrusted client-side hints — mutation
    safety lives in the in-band confirmation gate, never here): reads are
    read-only and idempotent; writes are (blanket) destructive; couplefins
    acts only on the couple's own data, so the world is closed.
    """
    is_read = spec.kind == "read"
    return ToolAnnotations(
        read_only_hint=is_read,
        destructive_hint=spec.kind == "write",
        idempotent_hint=is_read,
        open_world_hint=False,
    )


def exposed_specs() -> list[ToolSpec]:
    """Registry tools exposed over MCP — reads + writes, never agentic."""
    return [spec for spec in REGISTRY if mcp_exposure(spec) == "exposed"]


def _to_mcp_tool(spec: ToolSpec) -> Tool:
    """Build the MCP ``Tool`` for a registry spec, augmenting write schemas."""
    input_schema: dict[str, object] = dict(
        cast(Mapping[str, object], spec.schema["input_schema"])
    )
    if spec.kind == "write":
        existing = input_schema.get("properties")
        properties: dict[str, object] = (
            dict(cast(Mapping[str, object], existing))
            if isinstance(existing, Mapping)
            else {}
        )
        properties.update(_CONFIRM_PROPERTIES)
        input_schema["properties"] = properties
    return Tool(
        name=spec.name,
        description=str(spec.schema["description"]),
        input_schema=input_schema,
        annotations=mcp_annotations(spec),
    )


def _validate_no_confirm_collisions() -> None:
    """Fail at import if a write tool declares the injected field names.

    ``properties.update(_CONFIRM_PROPERTIES)`` would silently replace such a
    property and ``handle_write_call`` would consume its value before the
    handler ran — the tool would keep working in chat and break only over
    MCP, with no test to catch the divergence.
    """
    for spec in exposed_specs():
        if spec.kind != "write":
            continue
        schema = cast(Mapping[str, object], spec.schema["input_schema"])
        props = cast(Mapping[str, object], schema.get("properties") or {})
        overlap = _CONFIRM_PROPERTIES.keys() & props.keys()
        if overlap:
            raise ValueError(
                f"{spec.name}: input_schema declares reserved MCP confirmation "
                f"field(s) {sorted(overlap)}"
            )


_validate_no_confirm_collisions()

# The registry is immutable for the process lifetime — build the wire-format
# tool list once, not on every tools/list request.
_MCP_TOOLS: Final[list[Tool]] = [_to_mcp_tool(spec) for spec in exposed_specs()]


def _text_result(payload: object, *, is_error: bool = False) -> CallToolResult:
    """Wrap a JSON-serialisable result as a single-text-block CallToolResult."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return CallToolResult(
        content=[TextContent(type="text", text=text)], is_error=is_error
    )


class _PersonsCache:
    """The persons list, refreshed at most once per TTL window.

    Per-call resolution kept the server stateless (a renamed person is
    picked up without a restart), but with the Neon pooler endpoint the
    engine uses NullPool — every ``execute_use_case`` opens a fresh TLS
    connection, so an uncached lookup taxed every tool call with a remote
    connection handshake. A short TTL keeps both properties: renames land
    within a minute, and back-to-back tool calls pay the lookup once.
    Failures are never cached — an exception leaves the stale-at marker
    untouched, so the next call retries.
    """

    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._loaded_at: float | None = None
        self._persons: list[Person] = []
        self._refresh_lock = anyio.Lock()

    def _fresh(self) -> bool:
        return (
            self._loaded_at is not None
            and time.monotonic() - self._loaded_at < self._ttl
        )

    async def get(self) -> list[Person]:
        if self._fresh():
            return self._persons
        # The SDK dispatches each request in its own task; double-checked
        # locking collapses a stale-TTL burst into one remote fetch.
        async with self._refresh_lock:
            if not self._fresh():
                result = await execute_use_case(list_persons)
                self._persons = result.persons
                # An empty couple (pre-setup) is never cached: the next call
                # retries so setup completing in the web app lands
                # immediately instead of after a full TTL.
                if result.persons:
                    self._loaded_at = time.monotonic()
        return self._persons


_persons_cache = _PersonsCache()


async def _resolve_context(person_name: str) -> ToolContext:
    """Resolve the acting person (by name, case-insensitive) from the DB."""
    persons = await _persons_cache.get()
    try:
        match = resolve_person(person_name, persons)
    except ToolExecutionError as e:
        raise ToolExecutionError(f"{e} (check {ENV_PERSON})") from e
    return ToolContext(current_user=match, persons=persons, llm=_UnavailableLLM())


async def _handle_list_tools(
    _context: ServerRequestContext[object, PaginatedRequestParams],
    _params: PaginatedRequestParams,
) -> ListToolsResult:
    """Return every exposed tool. No pagination — the registry is small (~31)."""
    return ListToolsResult(tools=_MCP_TOOLS)


def _build_call_handler(person_name: str):
    """Bind the acting person name into the tools/call handler."""
    exposed = {spec.name: spec for spec in exposed_specs()}

    async def _handle_call_tool(
        _context: ServerRequestContext[object, CallToolRequestParams],
        params: CallToolRequestParams,
    ) -> CallToolResult:
        arguments: dict[str, object] = dict(params.arguments or {})
        spec = exposed.get(params.name)
        if spec is None:
            return _text_result(
                {"error": f"Unknown tool: {params.name}"}, is_error=True
            )
        try:
            ctx = await _resolve_context(person_name)
            if spec.kind == "write":
                result: dict[str, object] = await handle_write_call(
                    spec, arguments, ctx
                )
            else:
                result = await execute_tool(spec.name, arguments, ctx)
        except DomainError as e:
            # Actionable error as a tool result (the client's model
            # self-corrects in-turn), not a protocol error. Covers
            # ToolExecutionError AND the domain errors executors raise
            # directly on the commit path (ValidationError,
            # PeriodFinalizedError, ...) — the web route maps those via
            # FastAPI exception handlers; MCP has only this except.
            return _text_result({"error": str(e)}, is_error=True)
        except Exception:
            # A bug must not escape as a protocol-level failure in a
            # long-lived stdio session (and on the commit path the confirm
            # token is already consumed) — log it, answer in-band. Same
            # posture as the chat loop's broad catch (use_case.py).
            logger.exception("mcp_tool_call_failed", tool=params.name)
            return _text_result(
                {"error": f"Internal error executing {params.name}"}, is_error=True
            )
        # Strip <user_data> tags before they reach the client (covers read
        # results and the write-preview payload). The tags are a chat-side
        # prompt-injection defense the chat model is taught to read; an MCP
        # client is untaught, so here they are noise, not defense.
        return _text_result(strip_user_data(result))

    return _handle_call_tool


def build_server(person_name: str) -> Server[object]:
    """Assemble the MCP server acting as ``person_name`` (from the env)."""
    server: Server[object] = Server(SERVER_NAME)
    server.add_request_handler("tools/list", PaginatedRequestParams, _handle_list_tools)
    server.add_request_handler(
        "tools/call", CallToolRequestParams, _build_call_handler(person_name)
    )
    return server


async def serve_stdio(person_name: str) -> None:
    """Run the MCP server over stdio until the client disconnects."""
    server = build_server(person_name)
    logger.info(
        "mcp_server_start",
        person=person_name,
        tool_count=len(_MCP_TOOLS),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
