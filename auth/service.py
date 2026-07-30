"""
auth/service.py — Password hashing, JWT creation/decoding, and user CRUD.
"""
import psycopg
from datetime import datetime, timedelta
from typing import Optional

# ── passlib / bcrypt compatibility patch ─────────────────────────────────────
# passlib 1.7.4 references bcrypt.__about__.__version__ which was removed in
# bcrypt 4.0.  Re-inject the attribute so passlib can read the version cleanly.
import bcrypt as _bcrypt_mod
if not hasattr(_bcrypt_mod, "__about__"):
    _bcrypt_mod.__about__ = type(
        "about", (), {"__version__": _bcrypt_mod.__version__}
    )()

# Intercept and truncate passwords > 72 bytes to avoid ValueError in newer bcrypt versions
_orig_hashpw = _bcrypt_mod.hashpw
def _patched_hashpw(password, salt):
    if isinstance(password, bytes) and len(password) > 72:
        password = password[:72]
    elif isinstance(password, str) and len(password.encode("utf-8")) > 72:
        encoded = password.encode("utf-8")[:72]
        password = encoded.decode("utf-8", errors="ignore")
    return _orig_hashpw(password, salt)
_bcrypt_mod.hashpw = _patched_hashpw
# ─────────────────────────────────────────────────────────────────────────────

from jose import jwt
from passlib.context import CryptContext

from auth.models import get_db
from auth.schemas import UserOut
from config import get_settings

_settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode a signed JWT. `data` should contain at minimum {"sub": "<user_id>"}."""
    payload = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(hours=_settings.jwt_expire_hours)
    )
    payload["exp"] = expire
    return jwt.encode(payload, _settings.jwt_secret_key, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, _settings.jwt_secret_key, algorithms=[_settings.jwt_algorithm])


# ── User CRUD ─────────────────────────────────────────────────────────────────

def _row_to_user(row: dict) -> UserOut:
    created_at = row.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at or "")
    return UserOut(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        is_active=bool(row["is_active"]),
        created_at=created_at_str,
    )


def register_user(username: str, email: str, password: str) -> UserOut:
    """Create a new user. Raises psycopg.IntegrityError on duplicate username/email."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            hashed = hash_password(password)
            cur.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)",
                (username, email, hashed),
            )
            conn.commit()
            cur.execute(
                "SELECT * FROM users WHERE username = %s", (username,)
            )
            row = cur.fetchone()
            return _row_to_user(row)
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[UserOut]:
    """Return UserOut if credentials are valid, else None."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE username = %s", (username,)
            )
            row = cur.fetchone()
            if row is None or not verify_password(password, row["hashed_password"]):
                return None
            return _row_to_user(row)
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[UserOut]:
    """Fetch a user by primary key."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE id = %s", (user_id,)
            )
            row = cur.fetchone()
            return _row_to_user(row) if row else None
    finally:
        conn.close()
