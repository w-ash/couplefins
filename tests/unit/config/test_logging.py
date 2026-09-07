from collections.abc import Generator
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from src.config.logging import setup_logging
from src.config.settings import LoggingConfig, Settings


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Generator[None]:
    """Undo setup_logging()'s global effects.

    ``_configure_root`` clears the root logger's handlers, which would
    otherwise swallow pytest's capture handlers for the rest of the session.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def _use_logging_config(monkeypatch: pytest.MonkeyPatch, config: LoggingConfig) -> None:
    """Pin the logging config, so a developer's .env cannot change the result."""
    settings = Settings(logging=config)
    monkeypatch.setattr("src.config.logging.get_settings", lambda: settings)


def _file_handlers() -> list[RotatingFileHandler]:
    return [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]


def test_no_file_handler_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The deployed container relies on this: stdout only, and nothing written
    # to a disk that disappears on restart.
    _use_logging_config(monkeypatch, LoggingConfig())
    monkeypatch.chdir(tmp_path)

    setup_logging()

    assert _file_handlers() == []
    assert not (tmp_path / "logs").exists()
    assert len(logging.getLogger().handlers) == 1


def test_file_handler_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_file = tmp_path / "nested" / "couplefins.log"
    _use_logging_config(monkeypatch, LoggingConfig(file_path=log_file))

    setup_logging()

    handlers = _file_handlers()
    assert len(handlers) == 1
    assert Path(handlers[0].baseFilename) == log_file
    # The parent directory is created rather than assumed to exist.
    assert log_file.parent.is_dir()
