# =============================================================================
# FFIA — api/routers/auth.py
# Login and current-user endpoints.
# Reuses verify_password() from app/utils/auth.py (no Streamlit dependency).
# JWT issued with python-jose HS256.
# =============================================================================

# Step 1: Imports
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt

from api.deps import get_auth_users, get_current_user
from api.schemas import LoginRequest, LoginResponse, MeResponse

# Step 2: Router
router = APIRouter()

# Step 3: JWT config — mirrors guard in api/deps.py
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_jwt_secret_raw = os.getenv("JWT_SECRET", "")
if not _jwt_secret_raw:
    if _ENVIRONMENT == "production":
        raise RuntimeError(
            "JWT_SECRET must be set in production. "
            'Generate one with: python3 -c "import secrets; print(secrets.token_hex(32))"'
        )
    _jwt_secret_raw = "ffia-dev-secret-change-in-production"
_JWT_SECRET = _jwt_secret_raw
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 8


def _create_token(user_id: str, display_name: str) -> str:
    """Issue a signed JWT with 8-hour expiry."""
    payload = {
        "sub": user_id,
        "display_name": display_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


# Step 4: POST /auth/login
@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Validate PBKDF2 credentials and return a JWT."""
    from app.utils.auth import verify_password  # type: ignore[import]

    users = get_auth_users()
    user = users.get(body.username.strip())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = _create_token(user["user_id"], user["display_name"])
    return LoginResponse(
        access_token=token,
        user_id=user["user_id"],
        display_name=user["display_name"],
    )


# Step 5: GET /auth/me
@router.get("/me", response_model=MeResponse)
def me(current_user: dict = Depends(get_current_user)):
    """Decode the current JWT and return the user profile."""
    return MeResponse(
        user_id=current_user["user_id"],
        display_name=current_user["display_name"],
    )
