import hashlib
import hmac
import json
import os
import sys
import time
import streamlit as st


_AUTH_USERS_ENV = "FFIA_AUTH_USERS_JSON"
_LEGACY_OWNER_ENV = "FFIA_LEGACY_OWNER_USERNAME"
_PBKDF2_PREFIX = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 390000


def hash_password(password: str, salt_hex: str | None = None, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Create a PBKDF2-SHA256 password hash for auth configuration."""
    salt_hex = salt_hex or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    ).hex()
    return f"{_PBKDF2_PREFIX}${iterations}${salt_hex}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a PBKDF2-SHA256 hash."""
    # Step 1: Timing instrumentation — logs to terminal to profile PBKDF2 cost
    _t0 = time.perf_counter()
    try:
        scheme, iteration_str, salt_hex, expected_hex = stored_hash.split("$", 3)
        if scheme != _PBKDF2_PREFIX:
            return False
        iterations = int(iteration_str)
        candidate_hex = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        ).hex()
        result = hmac.compare_digest(candidate_hex, expected_hex)
    except (TypeError, ValueError):
        result = False
    finally:
        _elapsed_ms = (time.perf_counter() - _t0) * 1000
        print(f"[AUTH] verify_password: {_elapsed_ms:.1f}ms", file=sys.stderr)
    return result


def _is_supported_password_hash(stored_hash: str) -> bool:
    """Validate that the configured password hash uses the expected PBKDF2 format."""
    try:
        scheme, iteration_str, salt_hex, expected_hex = stored_hash.split("$", 3)
        if scheme != _PBKDF2_PREFIX:
            return False
        int(iteration_str)
        bytes.fromhex(salt_hex)
        bytes.fromhex(expected_hex)
        return True
    except (TypeError, ValueError):
        return False


# Step 2: Use @st.cache_resource instead of @lru_cache.
# st.cache_resource persists across Streamlit hot reloads (source file changes),
# whereas lru_cache is cleared when the module is reimported, forcing re-parsing
# of FFIA_AUTH_USERS_JSON and re-validation of all password hashes on the next login.
@st.cache_resource
def load_auth_users() -> dict[str, dict]:
    """
    Load configured login users from FFIA_AUTH_USERS_JSON.

    Expected format:
    [
      {
        "username": "alice",
        "password_hash": "pbkdf2_sha256$390000$...",
        "display_name": "Alice"
      }
    ]
    """
    raw_value = os.getenv(_AUTH_USERS_ENV, "").strip()
    if not raw_value:
        raise RuntimeError(
            f"{_AUTH_USERS_ENV} is not set. Configure at least one login user before starting FFIA."
        )

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{_AUTH_USERS_ENV} must be valid JSON: {exc}") from exc

    if not isinstance(parsed, list) or not parsed:
        raise RuntimeError(f"{_AUTH_USERS_ENV} must be a non-empty JSON array.")

    users: dict[str, dict] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            raise RuntimeError(f"{_AUTH_USERS_ENV} entries must be JSON objects.")

        username = str(entry.get("username", "")).strip()
        password_hash = str(entry.get("password_hash", "")).strip()
        display_name = str(entry.get("display_name", "")).strip() or username

        if not username or not password_hash:
            raise RuntimeError(
                f"{_AUTH_USERS_ENV} entries must include non-empty username and password_hash values."
            )
        if not _is_supported_password_hash(password_hash):
            raise RuntimeError(
                f"User '{username}' has an invalid password_hash format. "
                f"Expected {_PBKDF2_PREFIX}$iterations$salt_hex$hash_hex."
            )
        if username in users:
            raise RuntimeError(f"Duplicate username found in {_AUTH_USERS_ENV}: {username}")

        users[username] = {
            "user_id": username,
            "username": username,
            "display_name": display_name,
            "password_hash": password_hash,
        }

    return users


def authenticate_user(username: str, password: str) -> dict | None:
    """Return the authenticated public user profile, or None if credentials are invalid."""
    # Step 3: Timing instrumentation — total login cost including PBKDF2
    _t0 = time.perf_counter()

    normalized_username = str(username or "").strip()
    password = str(password or "")
    result = None

    if normalized_username and password:
        user = load_auth_users().get(normalized_username)
        if user and verify_password(password, user["password_hash"]):
            result = {
                "user_id": user["user_id"],
                "username": user["username"],
                "display_name": user["display_name"],
            }

    _elapsed_ms = (time.perf_counter() - _t0) * 1000
    print(f"[AUTH] authenticate_user total: {_elapsed_ms:.1f}ms", file=sys.stderr)
    return result


def get_legacy_owner_user_id() -> str | None:
    """
    Return the username that should own pre-tenant invoices during migration.

    Preference order:
    1. FFIA_LEGACY_OWNER_USERNAME
    2. The sole configured auth user, if exactly one exists
    """
    configured_owner = os.getenv(_LEGACY_OWNER_ENV, "").strip()
    if configured_owner:
        return configured_owner

    users = load_auth_users()
    if len(users) == 1:
        return next(iter(users))
    return None


def clear_auth_cache() -> None:
    """Reset cached auth config for tests or reload scenarios."""
    load_auth_users.clear()
