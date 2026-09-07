import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

import structlog

from src.config.settings import get_settings

_foreign_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]

_native_processors: list[structlog.types.Processor] = [
    structlog.stdlib.filter_by_level,
    *_foreign_processors,
]


def _make_formatter(
    renderer: structlog.types.Processor,
) -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_foreign_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )


def _configure_root(*handlers: logging.Handler, level: int | str) -> None:
    """The shared wiring: structlog pipeline + root handler installation.

    Both entry points below differ only in which handlers they build —
    the pipeline itself must stay identical or the MCP server's logs
    silently diverge from the web app's.
    """
    structlog.configure(
        processors=[
            *_native_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _make_file_handler(path: Path) -> logging.Handler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    handler.setFormatter(_make_formatter(structlog.processors.JSONRenderer()))
    return handler


def setup_logging() -> None:
    settings = get_settings().logging

    console_renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.output == "json"
        else structlog.dev.ConsoleRenderer()
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_make_formatter(console_renderer))

    handlers: list[logging.Handler] = [console_handler]
    if settings.file_path is not None:
        handlers.append(_make_file_handler(settings.file_path))

    _configure_root(*handlers, level=settings.level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def setup_stderr_logging() -> None:
    """Logging for stdio subprocesses (the MCP server).

    stdout is the JSON-RPC channel there — a single stray log line corrupts
    the protocol stream. Same structlog wiring as ``setup_logging`` but the
    console handler targets stderr and there is no file handler (the server
    is spawned from an arbitrary client cwd; don't scatter logs/ dirs).
    """
    settings = get_settings().logging

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(_make_formatter(structlog.processors.JSONRenderer()))

    _configure_root(stderr_handler, level=settings.level)
