"""
auth/routes.py — Authentication endpoints.

  POST /auth/register  — Create a new user account
  POST /auth/login     — Authenticate and receive a JWT
  GET  /auth/me        — Return current authenticated user info
"""
import psycopg

from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import require_auth
from auth.schemas import Token, UserLogin, UserOut, UserRegister
from auth.service import authenticate_user, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(body: UserRegister) -> UserOut:
    """Create a new user account.

    Returns the created user (without password).
    Raises **409 Conflict** if username or email is already taken.
    """
    try:
        return register_user(body.username, body.email, body.password)
    except psycopg.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists.",
        )


@router.post(
    "/login",
    response_model=Token,
    summary="Login and receive a JWT",
)
def login(body: UserLogin) -> Token:
    """Authenticate with username + password.

    Returns a signed Bearer JWT valid for the configured expiry window.
    Raises **401 Unauthorized** on wrong credentials.
    """
    user = authenticate_user(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user",
)
def get_me(current_user: UserOut = Depends(require_auth)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return current_user
