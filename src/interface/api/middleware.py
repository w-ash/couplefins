import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
import structlog

from src.domain.exceptions import (
    AuthenticationError,
    DomainError,
    DuplicateError,
    ForbiddenError,
    InvariantViolationError,
    NotFoundError,
    PeriodFinalizedError,
    ValidationError,
)

logger = structlog.get_logger()

_DOMAIN_ERROR_MAP: dict[type[DomainError], tuple[int, str]] = {
    NotFoundError: (404, "NOT_FOUND"),
    ValidationError: (422, "VALIDATION_ERROR"),
    DuplicateError: (409, "DUPLICATE_ERROR"),
    PeriodFinalizedError: (409, "PERIOD_FINALIZED"),
    AuthenticationError: (401, "AUTHENTICATION_ERROR"),
    ForbiddenError: (403, "FORBIDDEN"),
}


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        method: str = scope["method"]
        path: str = scope["path"]
        structlog.contextvars.bind_contextvars(method=method, path=path)

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=duration_ms,
            )


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, (status_code, error_code) in _DOMAIN_ERROR_MAP.items():
        _register_domain_handler(app, exc_type, status_code, error_code)

    @app.exception_handler(InvariantViolationError)
    async def invariant_error(_: Request, exc: InvariantViolationError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        logger.error("invariant_violation", detail=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INVARIANT_VIOLATION",
                    "message": "A calculation integrity check failed. "
                    "This is a bug — please check the server logs.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(_: Request, _exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        logger.error("unhandled_exception", exc_info=True)  # noqa: LOG014 — inside FastAPI exception handler
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                }
            },
        )


def _register_domain_handler(
    app: FastAPI,
    exc_type: type[DomainError],
    status_code: int,
    error_code: str,
) -> None:
    @app.exception_handler(exc_type)
    async def handler(_: Request, exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": error_code, "message": str(exc)}},
        )
