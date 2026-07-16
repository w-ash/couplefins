"""Config-snippet generation for registering the couplefins MCP server.

Every supported client wires an stdio MCP server the same way — a
``mcpServers`` map of ``{command, args, env}`` — so one snippet builder
serves them all; only the human guidance (where the config lives) differs
per client. Kept pure and side-effect-free so it is unit-testable and
``install`` never writes another app's config file itself.

Couplefins is not an installed CLI, so the server launches through uv from
the repo checkout: ``uv --directory <repo> run python -m src.interface.mcp``.
The acting person rides in ``COUPLEFINS_MCP_PERSON``.
"""

from pathlib import Path
import shutil

_REPO_ROOT = Path(__file__).resolve().parents[3]

# client key -> (display label, where the config lives). Claude Code
# registers via a command, not a file — its guidance is the command itself.
CLIENTS: dict[str, tuple[str, str]] = {
    "claude-code": ("Claude Code", "registered via the `claude mcp add` command"),
    "claude-desktop": (
        "Claude Desktop",
        "~/Library/Application Support/Claude/claude_desktop_config.json",
    ),
    "cursor": ("Cursor", "~/.cursor/mcp.json"),
}
SUPPORTED_CLIENTS: tuple[str, ...] = tuple(CLIENTS)


def _resolve_uv_command() -> str:
    """Absolute path to ``uv``, or the bare name as a fallback.

    GUI clients (Claude Desktop, Cursor) spawn the server with launchd's
    minimal PATH, which usually excludes the Homebrew bin where ``uv``
    lives — a bare ``{"command": "uv"}`` then fails ENOENT. ``install``
    runs in the user's own shell, so ``which()`` here sees the real PATH.
    """
    return shutil.which("uv") or "uv"


def server_entry(person_name: str) -> dict[str, object]:
    """The single couplefins server entry: launch the module over stdio."""
    return {
        "command": _resolve_uv_command(),
        "args": [
            "--directory",
            str(_REPO_ROOT),
            "run",
            "python",
            "-m",
            "src.interface.mcp",
        ],
        "env": {"COUPLEFINS_MCP_PERSON": person_name},
    }


def build_client_config(person_name: str) -> dict[str, object]:
    """The ``mcpServers`` snippet a client merges into its config."""
    return {"mcpServers": {"couplefins": server_entry(person_name)}}


def claude_code_command(person_name: str) -> str:
    """The ``claude mcp add`` one-liner (env must travel on the command)."""
    return (
        f"claude mcp add couplefins --env COUPLEFINS_MCP_PERSON={person_name} "
        f"-- {_resolve_uv_command()} --directory {_REPO_ROOT} run python -m "
        "src.interface.mcp"
    )
