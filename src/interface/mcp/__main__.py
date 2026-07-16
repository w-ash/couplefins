"""Entrypoint: ``python -m src.interface.mcp [install [person]]``.

Default (no args): serve MCP over stdio. Intended to be launched by an MCP
client as a subprocess, not run by hand — stdout carries JSON-RPC, so all
logging is routed to stderr before anything else imports a logger.

``install [person] [client]``: print the config snippet + registration
guidance for an MCP client (stdout is fine there — it's a human terminal).
"""

import asyncio
import contextlib
import json
import os
import sys

from src.config.logging import setup_stderr_logging

_ENV_PERSON = "COUPLEFINS_MCP_PERSON"


def _serve() -> None:
    setup_stderr_logging()
    person_name = os.environ.get(_ENV_PERSON, "").strip()
    if not person_name:
        print(
            f"{_ENV_PERSON} is not set. Set it to your person name "
            "(the name you log into Couplefins with) and relaunch.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    from src.interface.mcp.server import serve_stdio

    # Client-driven shutdown (the MCP client kills the subprocess) surfaces
    # as KeyboardInterrupt/EOF — exit quietly rather than dumping a traceback.
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve_stdio(person_name))


def _install(argv: list[str]) -> None:
    from src.interface.mcp.install import (
        CLIENTS,
        SUPPORTED_CLIENTS,
        build_client_config,
        claude_code_command,
    )

    person_name = argv[0] if argv else os.environ.get(_ENV_PERSON, "").strip()
    if not person_name:
        print(
            "Usage: python -m src.interface.mcp install <person> [client]\n"
            f"(or set {_ENV_PERSON})",
            file=sys.stderr,
        )
        raise SystemExit(2)
    client = argv[1] if len(argv) > 1 else "claude-code"
    if client not in SUPPORTED_CLIENTS:
        print(
            f"Unknown client {client!r}. Supported: {', '.join(SUPPORTED_CLIENTS)}",
            file=sys.stderr,
        )
        raise SystemExit(2)

    label, location = CLIENTS[client]
    if client == "claude-code":
        print(f"# {label} — run:")
        print(claude_code_command(person_name))
    else:
        print(f"# {label} — merge into {location}:")
        print(json.dumps(build_client_config(person_name), indent=2))


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "install":
        _install(args[1:])
    else:
        _serve()


if __name__ == "__main__":
    main()
