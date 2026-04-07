import time
from typing import cast

from starlette.types import ASGIApp, Message, Receive, Scope, Send
import structlog
from structlog.stdlib import get_logger

logger = get_logger()


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        method = cast(str, scope["method"])
        path = cast(str, scope["path"])
        structlog.contextvars.bind_contextvars(method=method, path=path)

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = cast(int, message["status"])
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
