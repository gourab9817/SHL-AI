import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging() -> None:
    """Configure application logging once for local and hosted runtimes."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log HTTP requests and responses without storing conversation state."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        path = request.url.path
        method = request.method

        response = await call_next(request)

        duration = time.time() - start_time
        status_code = response.status_code

        logger = logging.getLogger("app.request")
        logger.info(
            "%s %s - %s (%.2fs)",
            method,
            path,
            status_code,
            duration,
        )

        return response
