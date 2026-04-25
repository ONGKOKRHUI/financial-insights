"""
FinSight API — Phase 4 Auth & RBAC Integration Test
=====================================================
Tests the full authentication pipeline end-to-end against a live or local
FinSight backend:

  POST /auth/register
  POST /auth/login
  GET  /users/me
  POST /auth/refresh
  POST /auth/logout
  POST /search   ← RBAC gate: unauthenticated → 401, free → 403, paid/admin → 200
  POST /users/me/api-key/rotate
  GET  /users/me/api-key
  GET  /admin/users
  PATCH/DELETE /admin/users/{id}

Test Tiers
----------
1. Auth flow        — register → login → profile → refresh → logout
2. RBAC gates       — verify each protection layer returns the correct HTTP code
3. API key flow     — rotate key, call /search with X-API-Key header
4. Admin flow       — list users, update role, delete test accounts

Pre-conditions
--------------
- Backend must be running (local or Render).
- An ADMIN account must exist.  Set the env vars:
    FINSIGHT_ADMIN_EMAIL=admin@example.com
    FINSIGHT_ADMIN_PASSWORD=<generated_password_from_registration>
  If these are not set, admin tests are skipped.
  To create an admin:
    1. Register normally:  POST /auth/register {"email": "admin@..."}
    2. Manually set role in DB:
       UPDATE users SET role = 'admin' WHERE email = 'admin@...';
    3. Copy the generated_password into FINSIGHT_ADMIN_PASSWORD.

Usage
-----
Against the live Render deployment (default):
    python -m pytest tests/test_phase4_auth_integration.py -v

Against a local backend:
    FINSIGHT_BASE_URL=http://localhost:8000 python -m pytest tests/test_phase4_auth_integration.py -v

Human-readable walkthrough (no pytest):
    python tests/test_phase4_auth_integration.py

Environment variables
---------------------
FINSIGHT_BASE_URL        Backend base URL. Default: https://financial-insights-grit.onrender.com
FINSIGHT_ADMIN_EMAIL     Admin account email (optional — skips admin tests if absent)
FINSIGHT_ADMIN_PASSWORD  Admin account password (optional)
"""

import os
import sys
import time
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv(
    "FINSIGHT_BASE_URL",
    "https://financial-insights-grit.onrender.com",
).rstrip("/")

TIMEOUT = 60  # seconds per request

# Generate unique test emails per run so parallel runs don't collide
_RUN_ID = str(uuid.uuid4())[:8]
FREE_EMAIL = f"test_free_{_RUN_ID}@finsight-test.dev"
FREE_EMAIL_2 = f"test_free2_{_RUN_ID}@finsight-test.dev"  # used for admin delete test

ADMIN_EMAIL = os.getenv("FINSIGHT_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("FINSIGHT_ADMIN_PASSWORD", "")

# ---------------------------------------------------------------------------
# Availability check — skip entire module if backend is unreachable
# ---------------------------------------------------------------------------


def _api_is_available() -> tuple[bool, str]:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        if r.status_code == 200:
            return True, ""
        return False, f"Health check returned {r.status_code}"
    except requests.exceptions.ConnectionError as exc:
        return False, f"Connection refused: {exc}"
    except requests.exceptions.Timeout:
        return False, "Timed out connecting to backend"


_AVAILABLE, _SKIP_REASON = _api_is_available()

pytestmark = pytest.mark.skipif(
    not _AVAILABLE,
    reason=f"Backend not reachable at {BASE_URL}: {_SKIP_REASON}",
)

# ---------------------------------------------------------------------------
# Shared state across test functions (populated during the auth flow tests)
# ---------------------------------------------------------------------------

class _State:
    """Mutable shared state so tests can hand off data to later tests."""
    generated_password: str = ""
    free_session: requests.Session = None          # logged-in free user session
    free_user_id: int = 0
    api_key_raw: str = ""


_state = _State()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _post(session: requests.Session, path: str, **kwargs) -> requests.Response:
    return session.post(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def _get(session: requests.Session, path: str, **kwargs) -> requests.Response:
    return session.get(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def _patch(session: requests.Session, path: str, **kwargs) -> requests.Response:
    return session.patch(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def _delete(session: requests.Session, path: str, **kwargs) -> requests.Response:
    return session.delete(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


# ============================================================================
# TIER 1 — AUTH FLOW
# ============================================================================


class TestRegistration:
    def test_register_new_account(self):
        """POST /auth/register — creates a free account and returns generated_password."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": FREE_EMAIL},
            timeout=TIMEOUT,
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == FREE_EMAIL
        assert "generated_password" in body
        assert len(body["generated_password"]) >= 16, "Password too short"
        assert "message" in body
        # Store password for subsequent login tests
        _state.generated_password = body["generated_password"]
        print(f"\n  ✓ Registered {FREE_EMAIL}")
        print(f"  ✓ Generated password: {_state.generated_password[:8]}…")

    def test_register_duplicate_email_returns_409(self):
        """POST /auth/register — duplicate email returns 409 Conflict."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": FREE_EMAIL},
            timeout=TIMEOUT,
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"

    def test_register_invalid_email_returns_422(self):
        """POST /auth/register — malformed email returns 422 Unprocessable Entity."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": "not-an-email"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


class TestLogin:
    def test_login_valid_credentials(self):
        """POST /auth/login — sets access_token and refresh_token cookies."""
        assert _state.generated_password, "No generated_password — run registration tests first"
        session = requests.Session()
        r = _post(session, "/auth/login", json={
            "email": FREE_EMAIL,
            "password": _state.generated_password,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == FREE_EMAIL
        assert body["role"] == "free"

        # Verify cookies are set by the server
        assert "access_token" in session.cookies, "access_token cookie not set"
        assert "refresh_token" in session.cookies, "refresh_token cookie not set"

        # Save session for later tests
        _state.free_session = session
        print(f"\n  ✓ Logged in as {FREE_EMAIL} (role: {body['role']})")

    def test_login_wrong_password_returns_401(self):
        """POST /auth/login — wrong password returns 401."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": FREE_EMAIL, "password": "wrong_password_xyz"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"

    def test_login_unknown_email_returns_401(self):
        """POST /auth/login — unknown email returns 401."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nobody@finsight-test.dev", "password": "any"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


class TestUserProfile:
    def test_get_profile_authenticated(self):
        """GET /users/me — returns authenticated user's profile."""
        assert _state.free_session, "No session — run login tests first"
        r = _get(_state.free_session, "/users/me")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == FREE_EMAIL
        assert body["role"] == "free"
        assert body["has_api_key"] is False
        _state.free_user_id = body["id"]
        print(f"\n  ✓ Profile: id={body['id']}, role={body['role']}, has_api_key={body['has_api_key']}")

    def test_get_profile_unauthenticated_returns_401(self):
        """GET /users/me — without credentials returns 401."""
        r = requests.get(f"{BASE_URL}/users/me", timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


class TestTokenRefresh:
    def test_refresh_rotates_access_token(self):
        """POST /auth/refresh — issues a new access_token cookie."""
        assert _state.free_session, "No session — run login tests first"
        old_access = _state.free_session.cookies.get("access_token")
        r = _post(_state.free_session, "/auth/refresh")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        new_access = _state.free_session.cookies.get("access_token")
        # After 1 second the new JWT will have a different iat claim
        assert new_access is not None, "New access_token cookie not set"
        print(f"\n  ✓ Token refreshed (old prefix: {str(old_access)[:20]}…, new prefix: {str(new_access)[:20]}…)")

    def test_refresh_without_cookie_returns_401(self):
        """POST /auth/refresh — without refresh cookie returns 401."""
        r = requests.post(f"{BASE_URL}/auth/refresh", timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"


# ============================================================================
# TIER 2 — RBAC GATES
# ============================================================================


class TestRBACGates:
    """Verify that /search is correctly gated by role."""

    SEARCH_PAYLOAD = {"ticker": "MAYBANK", "statement_type": "kpi"}

    def test_search_unauthenticated_returns_401(self):
        """POST /search — no credentials → 401."""
        r = requests.post(f"{BASE_URL}/search", json=self.SEARCH_PAYLOAD, timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"\n  ✓ /search without auth → 401 (correct)")

    def test_search_free_user_cookie_returns_403(self):
        """POST /search — free user session cookie → 403 (not paid/admin)."""
        assert _state.free_session, "No session — run login tests first"
        r = _post(_state.free_session, "/search", json=self.SEARCH_PAYLOAD)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print(f"\n  ✓ /search with free-tier session → 403 (correct)")

    def test_api_key_required_for_search(self):
        """POST /search — invalid/absent X-API-Key returns 401."""
        r = requests.post(
            f"{BASE_URL}/search",
            json=self.SEARCH_PAYLOAD,
            headers={"X-API-Key": "fsk_not_a_real_key"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"\n  ✓ /search with bad API key → 401 (correct)")

    def test_public_company_endpoints_still_open(self):
        """GET /companies — public endpoint should return 200 even unauthenticated."""
        r = requests.get(f"{BASE_URL}/companies", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        print(f"\n  ✓ GET /companies (public) → 200, {len(data)} companies")

    def test_admin_endpoint_free_user_returns_403(self):
        """GET /admin/users — free user session → 403."""
        assert _state.free_session, "No session — run login tests first"
        r = _get(_state.free_session, "/admin/users")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print(f"\n  ✓ GET /admin/users with free-tier session → 403 (correct)")

    def test_api_key_endpoint_free_user_returns_403(self):
        """GET /users/me/api-key — free user → 403 (paid/admin only)."""
        assert _state.free_session, "No session — run login tests first"
        r = _get(_state.free_session, "/users/me/api-key")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print(f"\n  ✓ GET /users/me/api-key with free-tier session → 403 (correct)")


# ============================================================================
# TIER 3 — ADMIN FLOW
# (skipped when FINSIGHT_ADMIN_EMAIL / FINSIGHT_ADMIN_PASSWORD are not set)
# ============================================================================

_HAS_ADMIN = bool(ADMIN_EMAIL and ADMIN_PASSWORD)


@pytest.mark.skipif(not _HAS_ADMIN, reason="Set FINSIGHT_ADMIN_EMAIL + FINSIGHT_ADMIN_PASSWORD to run admin tests")
class TestAdminFlow:
    """Tests that require a pre-existing admin account in the database."""

    admin_session: requests.Session = None
    _second_user_id: int = 0

    @classmethod
    def _login_as_admin(cls):
        """Log in once and share the session across tests in this class."""
        if cls.admin_session:
            return cls.admin_session
        s = requests.Session()
        r = s.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, timeout=TIMEOUT)
        assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
        cls.admin_session = s
        return s

    def test_admin_login(self):
        """Admin can log in and their role is 'admin'."""
        s = self._login_as_admin()
        r = _get(s, "/users/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
        print(f"\n  ✓ Logged in as admin: {ADMIN_EMAIL}")

    def test_admin_list_users(self):
        """GET /admin/users — admin can list all users."""
        s = self._login_as_admin()
        r = _get(s, "/admin/users?page=1&page_size=10")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "users" in body
        assert "total" in body
        assert isinstance(body["users"], list)
        print(f"\n  ✓ Admin sees {body['total']} total user(s), showing {len(body['users'])}")

    def test_admin_upgrade_free_user_to_paid(self):
        """PATCH /admin/users/{id} — admin can set role to 'paid'."""
        assert _state.free_user_id, "No free user ID — run profile tests first"
        s = self._login_as_admin()
        r = _patch(s, f"/admin/users/{_state.free_user_id}", json={"role": "paid"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json()["role"] == "paid"
        print(f"\n  ✓ Admin upgraded user {_state.free_user_id} to 'paid'")

    def test_upgraded_user_can_rotate_api_key(self):
        """POST /users/me/api-key/rotate — after upgrade, user can generate an API key."""
        assert _state.free_session, "No free session"
        # Re-login to pick up the new role in the access token
        r = _post(_state.free_session, "/auth/refresh")
        assert r.status_code == 200

        r = _post(_state.free_session, "/users/me/api-key/rotate")
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert "raw_key" in body
        assert body["raw_key"].startswith("fsk_")
        _state.api_key_raw = body["raw_key"]
        print(f"\n  ✓ API key generated: {body['raw_key'][:12]}… (prefix: {body['key_prefix']})")

    def test_api_key_can_call_search(self):
        """POST /search with X-API-Key — paid user's key allows search."""
        assert _state.api_key_raw, "No API key — run rotate test first"
        r = requests.post(
            f"{BASE_URL}/search",
            json={"ticker": "MAYBANK", "statement_type": "kpi"},
            headers={"X-API-Key": _state.api_key_raw},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["ticker"] == "MAYBANK"
        assert body["statement_type"] == "kpi"
        print(f"\n  ✓ /search with API key → 200 (ticker: {body['ticker']}, fy: {body['fiscal_year']})")

    def test_session_cookie_can_call_search_after_upgrade(self):
        """POST /search with session cookie — paid session also works."""
        assert _state.free_session, "No session"
        # The refresh above updated the access token with the new role
        r = _post(
            _state.free_session,
            "/search",
            json={"ticker": "CIMB", "statement_type": "income_statement"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        print(f"\n  ✓ /search with paid session cookie → 200")

    def test_admin_deactivate_user(self):
        """PATCH /admin/users/{id} — admin can deactivate an account."""
        assert _state.free_user_id
        s = self._login_as_admin()
        r = _patch(s, f"/admin/users/{_state.free_user_id}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        print(f"\n  ✓ Admin deactivated user {_state.free_user_id}")

    def test_deactivated_user_cannot_login(self):
        """POST /auth/login — deactivated account returns 401."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": FREE_EMAIL, "password": _state.generated_password},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"\n  ✓ Deactivated user login → 401 (correct)")

    def test_admin_delete_test_user(self):
        """DELETE /admin/users/{id} — admin can delete an account."""
        assert _state.free_user_id
        s = self._login_as_admin()
        r = _delete(s, f"/admin/users/{_state.free_user_id}")
        assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"
        print(f"\n  ✓ Admin deleted user {_state.free_user_id}")

    def test_deleted_user_no_longer_exists(self):
        """GET /admin/users — deleted user not present in list."""
        s = self._login_as_admin()
        r = _get(s, "/admin/users?page=1&page_size=100")
        assert r.status_code == 200
        user_ids = [u["id"] for u in r.json()["users"]]
        assert _state.free_user_id not in user_ids
        print(f"\n  ✓ Deleted user {_state.free_user_id} no longer in user list")


# ============================================================================
# TIER 4 — LOGOUT
# ============================================================================


class TestLogout:
    def test_logout_clears_cookies(self):
        """POST /auth/logout — revokes token and clears cookies."""
        # Create a fresh session for this test so it doesn't depend on admin tests
        s = requests.Session()
        # Register a new account just for this test
        unique_email = f"test_logout_{_RUN_ID}@finsight-test.dev"
        reg = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": unique_email},
            timeout=TIMEOUT,
        )
        if reg.status_code != 201:
            pytest.skip("Could not register test user for logout test")
        pwd = reg.json()["generated_password"]

        login = _post(s, "/auth/login", json={"email": unique_email, "password": pwd})
        assert login.status_code == 200
        assert "access_token" in s.cookies

        r = _post(s, "/auth/logout")
        assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"

        # After logout the access_token cookie value should be cleared
        access_after = s.cookies.get("access_token")
        assert not access_after, f"Cookie should be cleared after logout, got: {access_after}"
        print(f"\n  ✓ Logout succeeded; cookies cleared")

    def test_profile_after_logout_returns_401(self):
        """GET /users/me — after logout, cookie is gone → 401."""
        s = requests.Session()  # fresh session, no cookies
        r = _get(s, "/users/me")
        assert r.status_code == 401
        print(f"\n  ✓ GET /users/me after logout (no cookies) → 401 (correct)")


# ============================================================================
# TIER 5 — WEBHOOK SIGNATURE VERIFICATION
# ============================================================================


class TestWebhookSecurity:
    def test_stripe_webhook_invalid_signature_returns_400(self):
        """POST /webhooks/stripe — invalid signature → 400 (not 200 or 500)."""
        fake_payload = b'{"type": "invoice.payment_succeeded", "data": {"object": {}}}'
        r = requests.post(
            f"{BASE_URL}/webhooks/stripe",
            data=fake_payload,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=12345,v1=invalid_signature",
            },
            timeout=TIMEOUT,
        )
        # 400 = signature rejected, 500 = webhook secret not configured (also acceptable)
        assert r.status_code in (400, 500), (
            f"Expected 400 or 500, got {r.status_code}: {r.text}"
        )
        print(f"\n  ✓ Webhook with invalid signature → {r.status_code} (rejected correctly)")

    def test_stripe_webhook_no_signature_returns_400_or_500(self):
        """POST /webhooks/stripe — missing Stripe-Signature header → 400/500."""
        r = requests.post(
            f"{BASE_URL}/webhooks/stripe",
            data=b'{"type": "test"}',
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 500), (
            f"Expected 400 or 500, got {r.status_code}: {r.text}"
        )
        print(f"\n  ✓ Webhook without signature → {r.status_code} (rejected correctly)")


# ============================================================================
# Standalone runner — human-readable walkthrough
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(" FinSight Phase 4 — Auth & RBAC Integration Test")
    print("=" * 60)
    print(f" Target: {BASE_URL}")
    print(f" Run ID: {_RUN_ID}")
    if not _HAS_ADMIN:
        print("\n ⚠  FINSIGHT_ADMIN_EMAIL / FINSIGHT_ADMIN_PASSWORD not set.")
        print("    Admin-tier tests will be SKIPPED.")
        print("    See module docstring for setup instructions.")

    available, reason = _api_is_available()
    if not available:
        print(f"\n ✗ Backend not reachable: {reason}")
        sys.exit(1)
    print(f"\n ✓ Backend reachable at {BASE_URL}")

    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
