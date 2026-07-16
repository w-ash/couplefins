"""Couplefins' MCP server — the second consumer of the shared tool registry.

``src/application/chat/registry.py`` is the single capability surface. The
in-app chat executor drives it today; this package exposes the same
``REGISTRY`` tuple over the Model Context Protocol (stdio) so any MCP-aware
client (Claude Code, Claude Desktop, Cursor) can read from and act on the
couple's Couplefins data.

The server is pure transport: it derives tool metadata + annotations from
the registry and dispatches through the existing ``execute_tool`` /
``execute_confirmed_action`` paths, inheriting handler validation and
two-phase mutation confirmation unchanged. It adds no tool logic of its own.

Scope (v1.9.3): read + write tools. ``agentic`` tools (sandbox, subagent,
tool search) are chat-executor concerns and are filtered out — an MCP
client brings its own agentic loop.

Accepted limitation: the server runs in its own process, so confirmed
writes cannot broadcast on the web app's in-memory EventBus — the 5-second
polling fallback on together-session pages picks the changes up instead.
"""
