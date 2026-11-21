import time
from collections import defaultdict
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces OWASP recommended security headers on all HTTP responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter protecting API endpoints from abuse and brute-force."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exempt CORS preflight and health checks
        if request.method == "OPTIONS" or request.url.path.endswith("/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        cutoff = now - self.window_seconds
        timestamps = [ts for ts in self.requests[client_ip] if ts > cutoff]
        self.requests[client_ip] = timestamps

        if len(timestamps) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(self.window_seconds)},
            )

        self.requests[client_ip].append(now)
        return await call_next(request)
