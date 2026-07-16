"""The single classifier for which registry tools the MCP server exposes.

Kept SDK-free (imports only ``ToolSpec``) so tests and any future
capability-matrix generator can import it without pulling the MCP SDK, and
so ``server.py``'s ``exposed_specs`` can never drift from the written
policy — one source of truth for MCP coverage.

v1.9.3: read + write tools are ``exposed``. ``agentic`` tools are
chat-executor concerns (the MCP client brings its own loop, sandbox, and
delegation). Couplefins has no long-running operations, so mixd's
``pending_tasks`` partition drops out entirely.
"""

from typing import Literal

from src.application.chat.registry import ToolSpec

type McpExposure = Literal["exposed", "agentic"]


def mcp_exposure(spec: ToolSpec) -> McpExposure:
    """Classify one registry tool's MCP exposure from its ``kind`` alone."""
    return "agentic" if spec.kind == "agentic" else "exposed"
