"""
MedRelay — Authentication & Authorization Module
JWT-based access/refresh tokens, bcrypt password hashing,
role-based access control, and account lockout.
"""

import hashlib
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    MAX_LOGIN_ATTEMPTS,
    LOGIN_LOCKOUT_MINUTES,
)
from backend.constants import ROLES, ROLE_PERMISSIONS, role_has_permission

# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify plaintext against bcrypt hash.
    Falls back to SHA-256 check for legacy migration.
    """
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Legacy SHA-256 fallback for unmigrated passwords
        legacy_hash = hashlib.sha256(plain.encode()).hexdigest()
        return legacy_hash == hashed


def is_bcrypt_hash(hashed: str) -> bool:
    """Check if a hash is bcrypt format (starts with $2b$)."""
    return hashed.startswith("$2b$") or hashed.startswith("$2a$")


# ── JWT Token Management ─────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str, role: str) -> str:
    """Create a short-lived JWT access token."""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token."""
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Rate Limiting / Account Lockout ──────────────────────────────────────────

# In-memory failed login tracker: { username: [(timestamp, ip), ...] }
_failed_attempts: dict[str, list[tuple[float, str]]] = defaultdict(list)


def record_failed_login(username: str, ip: str = "") -> None:
    """Record a failed login attempt."""
    _failed_attempts[username].append((time.time(), ip))


def clear_failed_logins(username: str) -> None:
    """Clear failed login history after successful login."""
    _failed_attempts.pop(username, None)


def is_account_locked(username: str) -> bool:
    """Check if an account is locked due to too many failed attempts."""
    attempts = _failed_attempts.get(username, [])
    cutoff = time.time() - (LOGIN_LOCKOUT_MINUTES * 60)
    # Only count recent attempts
    recent = [a for a in attempts if a[0] > cutoff]
    _failed_attempts[username] = recent
    return len(recent) >= MAX_LOGIN_ATTEMPTS


def get_lockout_remaining(username: str) -> int:
    """Return seconds remaining in lockout, or 0 if not locked."""
    attempts = _failed_attempts.get(username, [])
    if len(attempts) < MAX_LOGIN_ATTEMPTS:
        return 0
    cutoff = time.time() - (LOGIN_LOCKOUT_MINUTES * 60)
    recent = [a for a in attempts if a[0] > cutoff]
    if len(recent) < MAX_LOGIN_ATTEMPTS:
        return 0
    oldest = min(a[0] for a in recent)
    return max(0, int((oldest + LOGIN_LOCKOUT_MINUTES * 60) - time.time()))


# ── FastAPI Dependencies ─────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    Dependency — extract and validate JWT from Authorization header.
    Returns the decoded token payload dict with keys: sub, username, role, type.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — use an access token",
        )
    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """
    Dependency — returns user payload if a valid token is present, else None.
    Does NOT block unauthenticated access.
    """
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        return payload
    except HTTPException:
        return None


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency — requires the authenticated user to have 'admin' role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def require_nurse_or_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency — requires nurse or admin role."""
    if user.get("role") not in ("admin", "nurse"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nurse or admin privileges required",
        )
    return user


def require_permission(permission: str):
    """Dependency factory — requires the user to have a specific permission."""
    async def _guard(user: dict = Depends(get_current_user)) -> dict:
        if not role_has_permission(user.get("role", ""), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user
    return _guard


def require_any_role(*roles: str):
    """Dependency factory — requires the user to have one of the specified roles."""
    async def _guard(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {roles} required",
            )
        return user
    return _guard


# ── WebSocket Auth Helper ────────────────────────────────────────────────────

def authenticate_ws_token(token: str) -> dict:
    """
    Validate a JWT token from a WebSocket query param.
    Returns the payload dict or raises an exception.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError) as e:
        raise ValueError(f"WebSocket authentication failed: {e}")


# ── IP Rate Limiter ──────────────────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory per-IP rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
        if len(self._requests[ip]) >= self.max_requests:
            return False
        self._requests[ip].append(now)
        return True

    def get_retry_after(self, ip: str) -> int:
        if not self._requests.get(ip):
            return 0
        oldest = min(self._requests[ip])
        return max(0, int((oldest + self.window_seconds) - time.time()))


# Global rate limiters
api_rate_limiter = RateLimiter(max_requests=120, window_seconds=60)       # 120 req/min general
auth_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)       # 10 auth attempts/min
upload_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)      # 5 uploads/min
