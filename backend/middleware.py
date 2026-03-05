"""
MedRelay — Security Middleware
Rate limiting, security headers, request logging, and HIPAA-grade audit trail.
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

# ── HIPAA Audit Log ───────────────────────────────────────────────────────────
# Each entry is a JSON line written to an append-only file.
# MRN / patient identifiers are SHA-256 hashed before logging (PHI safeguard).
# Retain logs for >= 6 years per HIPAA §164.530(j).
_AUDIT_LOG_DIR  = os.path.join(os.path.dirname(__file__), "..", "logs")
_AUDIT_LOG_PATH = os.path.join(_AUDIT_LOG_DIR, "audit.log")
os.makedirs(_AUDIT_LOG_DIR, exist_ok=True)

# Endpoints that touch PHI — every hit must be audit-logged
_PHI_ENDPOINTS = {
    "/api/sessions", "/api/finalise", "/api/session",
    "/api/handoff",  "/api/sign",     "/ws/handoff",
    "/admin",
}

def _hash_phi(value: str) -> str:
    """One-way SHA-256 hash of a PHI string for audit log de-identification."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _write_audit(entry: dict) -> None:
    """Append a single JSON audit record to the audit log (thread-safe append)."""
    try:
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[AUDIT-ERROR] Failed to write audit log: {exc}")


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
    """
    HIPAA-grade audit logging middleware.

    For every request this middleware records:
      - ISO-8601 UTC timestamp
      - Unique request ID (X-Request-ID response header)
      - HTTP method + path + status code + latency
      - Client IP (hashed for PHI endpoints)
      - Authenticated user ID extracted from Bearer JWT payload (if present)
      - Session ID from path or query string (hashed)

    Records are written as JSON lines to logs/audit.log.
    PHI-adjacent endpoints trigger a full audit record; all other endpoints
    get a lightweight console log only.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        request.state.request_id = request_id

        response: Response = await call_next(request)

        elapsed_ms   = round((time.time() - start_time) * 1000, 1)
        method       = request.method
        path         = request.url.path
        status_code  = response.status_code
        response.headers["X-Request-ID"] = request_id

        # ── Console log (all non-health requests) ─────────────────────────────
        if path != "/health":
            level = "WARN" if status_code >= 400 else "INFO"
            print(f"[{level}] {request_id[:8]} {method} {path} → {status_code} ({elapsed_ms}ms)")

        # ── HIPAA audit log (PHI-adjacent endpoints) ──────────────────────────
        is_phi_endpoint = any(path.startswith(p) for p in _PHI_ENDPOINTS)
        if is_phi_endpoint:
            # Extract user identity from Authorization header (JWT sub claim)
            user_id = "anonymous"
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    import base64
                    payload_b64 = auth_header.split(".")[1]
                    # Add padding if needed
                    payload_b64 += "=" * (-len(payload_b64) % 4)
                    payload     = json.loads(base64.b64decode(payload_b64))
                    user_id     = payload.get("sub", payload.get("username", "unknown"))
                except Exception:
                    user_id = "parse-error"

            # Hash client IP for PHI endpoint logs (HIPAA safe-harbour de-id)
            raw_ip  = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            raw_ip  = raw_ip or (request.client.host if request.client else "unknown")
            client_ip_hash = _hash_phi(raw_ip)

            # Extract and hash session_id from path segments or query params
            session_id_raw = request.query_params.get("session_id", "")
            for segment in path.split("/"):
                if len(segment) == 36 and segment.count("-") == 4:  # UUID pattern
                    session_id_raw = segment
                    break
            session_ref = _hash_phi(session_id_raw) if session_id_raw else "none"

            audit_entry = {
                "ts":          datetime.now(timezone.utc).isoformat(),
                "request_id":  request_id,
                "user_id":     user_id,
                "action":      f"{method} {path}",
                "status":      status_code,
                "latency_ms":  elapsed_ms,
                "ip_hash":     client_ip_hash,
                "session_ref": session_ref,
                "outcome":     "SUCCESS" if status_code < 400 else "FAILURE",
            }
            _write_audit(audit_entry)

        return response
