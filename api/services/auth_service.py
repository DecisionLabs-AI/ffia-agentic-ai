"""Safe sandbox auth helpers for public demo user metadata."""

from __future__ import annotations

import json
import os
import hashlib
import hmac
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_AUTH_USERS_ENV = "FFIA_AUTH_USERS_JSON"
_PBKDF2_PREFIX = "pbkdf2_sha256"


def _is_supported_password_hash(stored_hash: str) -> bool:
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


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_auth_users() -> dict[str, dict[str, str]]:
    """Load auth users using the same shape as the Streamlit app.

    Mirrors the existing auth convention: username is the user_id. Secret fields
    are kept server-side only.
    """
    raw_value = os.getenv(_AUTH_USERS_ENV, "").strip()
    if not raw_value:
        raise ValueError("auth_not_configured")

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        raise ValueError("invalid_auth_config")

    if not isinstance(parsed, list):
        raise ValueError("invalid_auth_config")

    users: dict[str, dict[str, str]] = {}
    seen_usernames: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            raise ValueError("invalid_auth_config")

        username = _safe_text(entry.get("username"))
        password_hash = _safe_text(entry.get("password_hash"))
        display_name = _safe_text(entry.get("display_name")) or username
        restaurant_name = _safe_text(entry.get("restaurant_name"))

        if not username or not password_hash:
            raise ValueError("invalid_auth_config")
        if username in seen_usernames:
            raise ValueError("invalid_auth_config")
        if not _is_supported_password_hash(password_hash):
            raise ValueError("invalid_auth_config")

        users[username] = {
            "username": username,
            "user_id": username,
            "display_name": display_name,
            "password_hash": password_hash,
        }
        if restaurant_name:
            users[username]["restaurant_name"] = restaurant_name
        seen_usernames.add(username)

    return users


def _public_user(user: dict[str, str]) -> dict[str, str]:
    public_user = {
        "username": user["username"],
        "user_id": user["user_id"],
        "display_name": user.get("display_name") or user["username"],
    }
    if user.get("restaurant_name"):
        public_user["restaurant_name"] = user["restaurant_name"]
    return public_user


def get_demo_users() -> list[dict[str, str]]:
    """Return public user metadata from FFIA_AUTH_USERS_JSON."""
    try:
        return [_public_user(user) for user in _load_auth_users().values()]
    except ValueError:
        return []


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a PBKDF2-SHA256 hash."""
    try:
        scheme, iteration_str, salt_hex, expected_hex = stored_hash.split("$", 3)
        if scheme != _PBKDF2_PREFIX:
            return False
        candidate_hex = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iteration_str),
        ).hex()
        return hmac.compare_digest(candidate_hex, expected_hex)
    except (TypeError, ValueError):
        return False


def authenticate_demo_user(username: str, password: str) -> dict[str, str] | None:
    """Return the authenticated public user profile, or None."""
    try:
        users = _load_auth_users()
    except ValueError:
        return None

    user = users.get(_safe_text(username))
    if not user:
        return None
    if not verify_password(str(password or ""), user["password_hash"]):
        return None
    return _public_user(user)
