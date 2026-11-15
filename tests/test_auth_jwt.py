# =============================================================================
# FFIA — tests/test_auth_jwt.py
# Regression tests for JWT auth after migrating python-jose -> PyJWT.
# Covers: login -> token -> protected endpoint, and rejection of expired,
# wrong-secret and alg=none tokens.
# =============================================================================

# Step 1: Imports + test-only auth user (low PBKDF2 iterations to keep tests fast)
import base64
import json
import os
import unittest
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

from app.utils.auth import hash_password

_TEST_USER = "jwt_test_user"
_TEST_PASSWORD = "correct-horse-battery-staple"
os.environ["FFIA_AUTH_USERS_JSON"] = json.dumps([
    {
        "username": _TEST_USER,
        "password_hash": hash_password(_TEST_PASSWORD, iterations=1000),
        "display_name": "JWT Test",
    }
])

# Step 2: Import the app after env is set (api.main mocks Streamlit for routers)
from fastapi.testclient import TestClient  # noqa: E402

from api import deps  # noqa: E402
from api.main import app  # noqa: E402


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class AuthJwtTests(unittest.TestCase):
    # Step 3: Fresh client + clear cached user list so the test user is loaded
    def setUp(self):
        deps._load_auth_users.cache_clear()
        self.client = TestClient(app)

    def tearDown(self):
        deps._load_auth_users.cache_clear()

    def _me(self, token: str):
        return self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    def _payload(self, exp: datetime) -> dict:
        return {"sub": _TEST_USER, "display_name": "JWT Test", "exp": exp}

    # Step 4: Happy path — login returns a str token that unlocks /auth/me
    def test_login_token_grants_access(self):
        resp = self.client.post("/auth/login", json={"username": _TEST_USER, "password": _TEST_PASSWORD})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        self.assertIsInstance(token, str)
        self.assertEqual(jwt.get_unverified_header(token)["alg"], "HS256")

        me = self._me(token)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["user_id"], _TEST_USER)

    def test_wrong_password_rejected(self):
        resp = self.client.post("/auth/login", json={"username": _TEST_USER, "password": "nope"})
        self.assertEqual(resp.status_code, 401)

    # Step 5: Rejection cases
    def test_expired_token_rejected(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        token = jwt.encode(self._payload(past), deps._JWT_SECRET, algorithm="HS256")
        self.assertEqual(self._me(token).status_code, 401)

    def test_token_signed_with_other_secret_rejected(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        token = jwt.encode(self._payload(future), "not-the-server-secret-" + "x" * 16, algorithm="HS256")
        self.assertEqual(self._me(token).status_code, 401)

    def test_alg_none_token_rejected(self):
        future = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        header = _b64url({"alg": "none", "typ": "JWT"})
        body = _b64url({"sub": _TEST_USER, "display_name": "JWT Test", "exp": future})
        self.assertEqual(self._me(f"{header}.{body}.").status_code, 401)


if __name__ == "__main__":
    unittest.main()
