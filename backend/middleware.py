"""
MedRelay — Security Middleware
Rate limiting, security headers, and request logging.
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
        # Cache control for API responses
        if request.url.path.startswith("/api") or request.url.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global rate limiting middleware with per-IP tracking."""

    def __init__(self, app, max_requests: int = 200, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for CORS preflight, WebSocket upgrades, and health checks
        if request.method == "OPTIONS" or request.url.path in ("/health", "/ws/handoff"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean and count
        if ip not in self._requests:
            self._requests[ip] = []
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]

        if len(self._requests[ip]) >= self.max_requests:
            retry_after = int(min(self._requests[ip]) + self.window_seconds - now)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": max(1, retry_after),
                },
                headers={"Retry-After": str(max(1, retry_after))},
            )

        self._requests[ip].append(now)
        return await call_next(request)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        # Check for proxy headers
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request metadata for audit and debugging."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Attach request_id for downstream usage
        request.state.request_id = request_id

        response: Response = await call_next(request)

        elapsed = round((time.time() - start_time) * 1000, 1)
        method = request.method
        path = request.url.path
        status_code = response.status_code

        # Log non-health requests
        if path != "/health":
            level = "WARN" if status_code >= 400 else "INFO"
            print(f"[{level}] {request_id} {method} {path} → {status_code} ({elapsed}ms)")

        response.headers["X-Request-ID"] = request_id
        return response
