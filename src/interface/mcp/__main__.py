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
from src.interface.mcp.install import ENV_PERSON


def _person_from_env() -> str:
    """The acting person from the env var — the one read-and-normalize rule."""
    return os.environ.get(ENV_PERSON, "").strip()


def _serve() -> None:
    setup_stderr_logging()
    person_name = _person_from_env()
    if not person_name:
        print(
            f"{ENV_PERSON} is not set. Set it to your person name "
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

    # Client keys and person names share the positional slots, so both
    # orders are accepted: `install <person> [client]` and
    # `install <client> [person]`. A leading client key is never treated as
    # a person named "cursor" — silently embedding a client key as the
    # person would fail every tool call after registration.
    if argv and argv[0] in SUPPORTED_CLIENTS:
        client = argv[0]
        person_name = argv[1] if len(argv) > 1 else _person_from_env()
    else:
        person_name = argv[0] if argv else _person_from_env()
        client = argv[1] if len(argv) > 1 else "claude-code"
    if not person_name:
        print(
            "Usage: python -m src.interface.mcp install <person> [client]\n"
            f"(or set {ENV_PERSON} and pass just the client)",
            file=sys.stderr,
        )
        raise SystemExit(2)
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
    elif args:
        # A typo'd subcommand must not fall through to the stdio server —
        # that blocks silently on stdin waiting for JSON-RPC that never comes.
        print(
            f"Unknown command {args[0]!r}. "
            "Usage: python -m src.interface.mcp [install [person] [client]]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    else:
        _serve()


if __name__ == "__main__":
    main()
