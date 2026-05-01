# =============================================================================
# FFIA — api/deps.py
# Shared FastAPI dependency functions: JWT decoding, current user extraction.
# =============================================================================

# Step 1: Standard + third-party imports
import os
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

# Step 2: JWT config from environment
_JWT_SECRET = os.getenv("JWT_SECRET", "ffia-dev-secret-change-in-production")
_JWT_ALGORITHM = "HS256"
_bearer = HTTPBearer()


# Step 3: Load auth users — Streamlit-free version using lru_cache.
# Reimplements load_auth_users() from app/utils/auth.py without the
# @st.cache_resource decorator so it works in a non-Streamlit process.
@lru_cache(maxsize=1)
def _load_auth_users() -> dict[str, dict]:
    import json
    from app.utils.auth import _is_supported_password_hash  # type: ignore[import]

    raw = os.getenv("FFIA_AUTH_USERS_JSON", "").strip()
    if not raw:
        raise RuntimeError("FFIA_AUTH_USERS_JSON is not set.")
    parsed = json.loads(raw)
    users: dict[str, dict] = {}
    for entry in parsed:
        uname = str(entry.get("username", "")).strip()
        phash = str(entry.get("password_hash", "")).strip()
        dname = str(entry.get("display_name", "")).strip() or uname
        if not uname or not phash:
            continue
        if not _is_supported_password_hash(phash):
            continue
        users[uname] = {
            "user_id": uname,
            "username": uname,
            "display_name": dname,
            "password_hash": phash,
        }
    return users


def get_auth_users() -> dict[str, dict]:
    return _load_auth_users()


# Step 4: JWT decoder dependency — extracts user_id from Bearer token
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(creds.credentials, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        user_id: str = payload.get("sub", "")
        display_name: str = payload.get("display_name", user_id)
        if not user_id:
            raise credentials_error
    except JWTError:
        raise credentials_error
    return {"user_id": user_id, "display_name": display_name}


# Step 5: Convenience dependency — returns just the user_id string
def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    return user["user_id"]
