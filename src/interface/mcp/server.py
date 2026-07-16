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
var (a person name), resolved against the DB per call — couplefins'
``ToolContext`` carries a full ``Person`` plus the persons list, not a bare
id. Resolution failures surface as actionable tool errors.
"""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
import json
from typing import cast

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
from src.application.chat.user_data import strip_user_data
from src.application.runner import execute_use_case
from src.application.use_cases.list_persons import list_persons
from src.domain.entities.person import Person
from src.domain.exceptions import ToolExecutionError
from src.interface.mcp.confirmation import handle_write_call
from src.interface.mcp.exposure import mcp_exposure

logger = get_logger()

SERVER_NAME = "couplefins"

# Optional properties injected into every exposed write tool's schema so a
# client can drive the two-phase confirmation in-band. The base schemas set
# additionalProperties: false, so these must be declared as real properties.
_CONFIRM_PROPERTIES: dict[str, object] = {
    "confirm": {
        "type": "boolean",
        "description": (
            "Omit (or false) to preview the change and receive a confirm_token. "
            "Set true — with the confirm_token from that preview and the same "
            "arguments — to commit."
        ),
    },
    "confirm_token": {
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


def _text_result(payload: object, *, is_error: bool = False) -> CallToolResult:
    """Wrap a JSON-serialisable result as a single-text-block CallToolResult."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return CallToolResult(
        content=[TextContent(type="text", text=text)], is_error=is_error
    )


async def _resolve_context(person_name: str) -> ToolContext:
    """Resolve the acting person (by name, case-insensitive) from the DB.

    Per-call resolution keeps the server stateless across a long-lived
    client session — a renamed or newly-created person is picked up without
    a restart. Two rows; the query cost is negligible.
    """
    result = await execute_use_case(list_persons)
    persons: list[Person] = result.persons
    match = next((p for p in persons if p.name.lower() == person_name.lower()), None)
    if match is None:
        names = ", ".join(p.name for p in persons) or "(none configured)"
        raise ToolExecutionError(
            f"Unknown person {person_name!r} in COUPLEFINS_MCP_PERSON. "
            f"Configured persons: {names}"
        )
    return ToolContext(current_user=match, persons=persons, llm=_UnavailableLLM())


async def _handle_list_tools(
    _context: ServerRequestContext[object, PaginatedRequestParams],
    _params: PaginatedRequestParams,
) -> ListToolsResult:
    """Return every exposed tool. No pagination — the registry is small (~31)."""
    return ListToolsResult(tools=[_to_mcp_tool(spec) for spec in exposed_specs()])


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
        except ToolExecutionError as e:
            # Actionable error as a tool result (the client's model
            # self-corrects in-turn), not a protocol error.
            return _text_result({"error": str(e)}, is_error=True)
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
        tool_count=len(exposed_specs()),
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
