"""
auth/dependencies.py — FastAPI security dependencies.

require_auth() accepts EITHER:
  - A valid signed JWT token (user-based access)
  - A valid static API key (service-to-service access)

Usage:
    @app.post("/run")
    def run_agent(current_user: UserOut = Depends(require_auth)):
        ...
"""

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from auth.schemas import UserOut
from auth.service import decode_token, get_user_by_id
from config import get_settings

_settings = get_settings()
_bearer_scheme = HTTPBearer(auto_error=False)

# Sentinel UserOut returned when caller authenticates via static API key
_SERVICE_USER = UserOut(
    id=0,
    username="service",
    email="service@internal",
    is_active=True,
    created_at="",
)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> UserOut:
    """Validate the incoming Bearer token.

    Accepts:
    1. Static API key  — checked against settings.api_key
    2. Signed JWT      — decoded and verified; user fetched from DB

    Raises HTTP 401 on missing or invalid credentials.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── Layer 1: Static API key ───────────────────────────────────────────────
    if _settings.api_key and token == _settings.api_key:
        return _SERVICE_USER

    # ── Layer 2: JWT ──────────────────────────────────────────────────────────
    try:
        payload = decode_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = get_user_by_id(int(user_id_str))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
