from __future__ import annotations

import uuid
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable used by logging filter / adapters
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject/propagate a request id (correlation id).

    - If the client sends X-Request-ID (or configured header), we reuse it.
    - Otherwise we generate one.
    - We store it in a contextvar so logs can include it.
    - We also return it as a response header for easier tracing.
    """

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(self._header_name) or str(uuid.uuid4())
        token = request_id_ctx.set(rid)
        try:
            response: Response = await call_next(request)
            response.headers[self._header_name] = rid
            return response
        finally:
            request_id_ctx.reset(token)
