from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from structlog.stdlib import get_logger

from src.domain.exceptions import (
    AnthropicApiError,
    AuthenticationError,
    ChatUnavailableError,
    DomainError,
    DuplicateError,
    ForbiddenError,
    InvariantViolationError,
    MaxRoundsExceededError,
    NotFoundError,
    PeriodFinalizedError,
    RateLimitExceededError,
    ToolExecutionError,
    ValidationError,
)

logger = get_logger()

_DOMAIN_ERROR_MAP: dict[type[DomainError], tuple[int, str]] = {
    NotFoundError: (404, "NOT_FOUND"),
    ValidationError: (422, "VALIDATION_ERROR"),
    DuplicateError: (409, "DUPLICATE_ERROR"),
    PeriodFinalizedError: (409, "PERIOD_FINALIZED"),
    AuthenticationError: (401, "AUTHENTICATION_ERROR"),
    ForbiddenError: (403, "FORBIDDEN"),
    RateLimitExceededError: (429, "RATE_LIMIT_EXCEEDED"),
    ChatUnavailableError: (503, "CHAT_UNAVAILABLE"),
    ToolExecutionError: (500, "TOOL_EXECUTION_ERROR"),
    MaxRoundsExceededError: (400, "MAX_ROUNDS_EXCEEDED"),
    AnthropicApiError: (502, "ANTHROPIC_API_ERROR"),
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    mapping = _DOMAIN_ERROR_MAP.get(type(exc))
    if mapping is None:
        return _error_response(500, "INTERNAL_ERROR", "An internal error occurred")
    status_code, error_code = mapping
    return _error_response(status_code, error_code, str(exc))


async def _handle_invariant_error(
    _: Request, exc: InvariantViolationError
) -> JSONResponse:
    logger.error("invariant_violation", detail=str(exc))
    return _error_response(
        500,
        "INVARIANT_VIOLATION",
        "A calculation integrity check failed. This is a bug — please check the server logs.",
    )


async def _handle_unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", exc_info=exc)
    return _error_response(500, "INTERNAL_ERROR", "An internal error occurred")


def register_error_handlers(app: FastAPI) -> None:
    for exc_type in _DOMAIN_ERROR_MAP:
        app.exception_handler(exc_type)(_handle_domain_error)
    app.exception_handler(InvariantViolationError)(_handle_invariant_error)
    app.exception_handler(Exception)(_handle_unhandled_error)
