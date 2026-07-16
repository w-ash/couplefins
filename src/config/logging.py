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


def setup_logging() -> None:
    settings = get_settings().logging

    console_renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.output == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            *_native_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_make_formatter(console_renderer))

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "couplefins.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setFormatter(_make_formatter(structlog.processors.JSONRenderer()))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.setLevel(settings.level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def setup_stderr_logging() -> None:
    """Logging for stdio subprocesses (the MCP server).

    stdout is the JSON-RPC channel there — a single stray log line corrupts
    the protocol stream. Same structlog wiring as ``setup_logging`` but the
    console handler targets stderr and there is no file handler (the server
    is spawned from an arbitrary client cwd; don't scatter logs/ dirs).
    """
    settings = get_settings().logging

    structlog.configure(
        processors=[
            *_native_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(_make_formatter(structlog.processors.JSONRenderer()))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stderr_handler)
    root.setLevel(settings.level)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
