from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.domain.exceptions import (
    DomainError,
    DuplicateError,
    NotFoundError,
    PeriodFinalizedError,
    ValidationError,
)

_DOMAIN_ERROR_MAP: dict[type[DomainError], tuple[int, str]] = {
    NotFoundError: (404, "NOT_FOUND"),
    ValidationError: (422, "VALIDATION_ERROR"),
    DuplicateError: (409, "DUPLICATE_ERROR"),
    PeriodFinalizedError: (409, "PERIOD_FINALIZED"),
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, (status_code, error_code) in _DOMAIN_ERROR_MAP.items():
        _register_domain_handler(app, exc_type, status_code, error_code)

    @app.exception_handler(Exception)
    async def internal_error(_: Request, _exc: Exception) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        logger.opt(exception=True).error("Unhandled exception")
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
