"""
FinSight Phase 4 — Full-Stack Integration Tests
================================================
Tests the complete Phase 4 feature set against both layers:

  Layer A — FastAPI backend (direct)
    Verifies auth endpoints, RBAC, token lifecycle, admin operations.

  Layer B — Next.js BFF routes (when the frontend dev server is running)
    Verifies that the Next.js proxy routes correctly relay cookies,
    return the full AuthUser shape, and enforce auth on admin routes.

Test structure
--------------
Tier 1  Registration & duplicate/invalid email guards
Tier 2  Login — cookies set, full AuthUser shape returned
Tier 3  Token lifecycle — /auth/me, /auth/refresh, /auth/logout
Tier 4  RBAC gates — /search, /admin/users, /users/me/api-key
Tier 5  BFF routes — same flows via Next.js /api/** proxy (skipped unless
         FINSIGHT_FRONTEND_URL is set to a running Next.js instance)
Tier 6  Admin flow — list, upgrade, deactivate, delete users
Tier 7  Webhook security — Stripe signature verification

Pre-conditions
--------------
  - FastAPI backend must be running.
    Default target: https://financial-insights-grit.onrender.com
    Override:       FINSIGHT_BASE_URL=http://localhost:8000

  - Admin tests require a pre-created admin account:
    1. Register:   POST /auth/register  {"email": "admin@example.com"}
    2. Promote:    UPDATE users SET role='admin' WHERE email='admin@example.com';
    3. Export env: FINSIGHT_ADMIN_EMAIL / FINSIGHT_ADMIN_PASSWORD

  - BFF tests require the Next.js dev server to be running:
    Override:       FINSIGHT_FRONTEND_URL=http://localhost:3000

Usage
-----
# All tiers against the live Render backend:
  pytest tests/test_phase4_full_stack.py -v

# Against a local backend:
  FINSIGHT_BASE_URL=http://localhost:8000 pytest tests/test_phase4_full_stack.py -v

# With BFF tests (requires Next.js running):
  FINSIGHT_BASE_URL=http://localhost:8000 \
  FINSIGHT_FRONTEND_URL=http://localhost:3000 \
  pytest tests/test_phase4_full_stack.py -v

# Standalone human-readable walkthrough (no pytest):
  python tests/test_phase4_full_stack.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL: str = os.getenv(
    "FINSIGHT_BASE_URL",
    "https://financial-insights-grit.onrender.com",
).rstrip("/")

FRONTEND_URL: str = os.getenv("FINSIGHT_FRONTEND_URL", "").rstrip("/")

ADMIN_EMAIL: str = os.getenv("FINSIGHT_ADMIN_EMAIL", "")
ADMIN_PASSWORD: str = os.getenv("FINSIGHT_ADMIN_PASSWORD", "")

TIMEOUT: int = 60  # seconds

# Unique suffix per run — prevents email collisions across parallel runs.
_RUN_ID: str = str(uuid.uuid4())[:8]
FREE_EMAIL: str = f"test_free_{_RUN_ID}@finsight-test.dev"
LOGOUT_EMAIL: str = f"test_logout_{_RUN_ID}@finsight-test.dev"
ADMIN_DELETE_EMAIL: str = f"test_del_{_RUN_ID}@finsight-test.dev"

_HAS_ADMIN: bool = bool(ADMIN_EMAIL and ADMIN_PASSWORD)
_HAS_BFF: bool = bool(FRONTEND_URL)


# ---------------------------------------------------------------------------
# Availability guards
# ---------------------------------------------------------------------------

def _backend_available() -> tuple[bool, str]:
    """Return (available, reason) for the FastAPI backend."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        return (r.status_code == 200, f"HTTP {r.status_code}")
    except requests.ConnectionError as exc:
        return (False, f"Connection refused: {exc}")
    except requests.Timeout:
        return (False, "Timed out")


def _bff_available() -> tuple[bool, str]:
    """Return (available, reason) for the Next.js BFF server."""
    if not FRONTEND_URL:
        return (False, "FINSIGHT_FRONTEND_URL not set")
    try:
        r = requests.get(f"{FRONTEND_URL}/api/auth/me", timeout=10)
        # 401 is expected (no cookie) — the server is up.
        return (r.status_code in (200, 401), f"HTTP {r.status_code}")
    except requests.ConnectionError as exc:
        return (False, f"Connection refused: {exc}")
    except requests.Timeout:
        return (False, "Timed out")


_BACKEND_OK, _BACKEND_SKIP_REASON = _backend_available()

pytestmark = pytest.mark.skipif(
    not _BACKEND_OK,
    reason=f"Backend not reachable at {BASE_URL}: {_BACKEND_SKIP_REASON}",
)


# ---------------------------------------------------------------------------
# Shared mutable state — populated by earlier tests, consumed by later ones.
# ---------------------------------------------------------------------------

class _State:
    generated_password: str = ""
    free_session: requests.Session | None = None
    free_user_id: int = 0
    api_key_raw: str = ""


_state = _State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(s: requests.Session, path: str, base: str = BASE_URL, **kw) -> requests.Response:
    return s.post(f"{base}{path}", timeout=TIMEOUT, **kw)


def _get(s: requests.Session, path: str, base: str = BASE_URL, **kw) -> requests.Response:
    return s.get(f"{base}{path}", timeout=TIMEOUT, **kw)


def _patch(s: requests.Session, path: str, base: str = BASE_URL, **kw) -> requests.Response:
    return s.patch(f"{base}{path}", timeout=TIMEOUT, **kw)


def _delete(s: requests.Session, path: str, base: str = BASE_URL, **kw) -> requests.Response:
    return s.delete(f"{base}{path}", timeout=TIMEOUT, **kw)


# ============================================================================
# TIER 1 — REGISTRATION
# ============================================================================

class TestRegistration:
    """POST /auth/register — account creation, duplicate guard, email validation."""

    def test_register_new_account(self):
        """Creates a free account and returns a generated password."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": FREE_EMAIL},
            timeout=TIMEOUT,
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == FREE_EMAIL, "Email mismatch in response"
        assert "generated_password" in body, "generated_password missing from response"
        assert len(body["generated_password"]) >= 16, "Generated password too short"
        assert "message" in body, "message field missing"
        _state.generated_password = body["generated_password"]
        print(f"\n  ✓ Registered {FREE_EMAIL} — password length {len(_state.generated_password)}")

    def test_register_duplicate_email_returns_409(self):
        """Duplicate email registration returns HTTP 409 Conflict."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": FREE_EMAIL},
            timeout=TIMEOUT,
        )
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
        print("\n  ✓ Duplicate email → 409 (correct)")

    def test_register_invalid_email_returns_422(self):
        """Malformed email returns HTTP 422 Unprocessable Entity."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": "not-an-email"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
        print("\n  ✓ Invalid email → 422 (correct)")

    def test_register_missing_body_returns_422(self):
        """Missing request body returns HTTP 422."""
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json={},
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
        print("\n  ✓ Missing email field → 422 (correct)")


# ============================================================================
# TIER 2 — LOGIN
# ============================================================================

class TestLogin:
    """POST /auth/login — credential validation, cookie issuance, error cases."""

    def test_login_sets_cookies(self):
        """Valid credentials set access_token and refresh_token cookies."""
        assert _state.generated_password, "Run registration tests first"
        session = requests.Session()
        r = _post(session, "/auth/login", json={
            "email": FREE_EMAIL,
            "password": _state.generated_password,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("email") == FREE_EMAIL, "email missing from login response"
        assert body.get("role") == "free", f"Expected role 'free', got {body.get('role')}"

        assert "access_token" in session.cookies, "access_token cookie not set"
        assert "refresh_token" in session.cookies, "refresh_token cookie not set"

        _state.free_session = session
        print(f"\n  ✓ Login OK — role={body['role']}, both cookies present")

    def test_login_wrong_password_returns_401(self):
        """Wrong password returns HTTP 401."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": FREE_EMAIL, "password": "definitely_wrong"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ Wrong password → 401 (correct)")

    def test_login_unknown_email_returns_401(self):
        """Unknown email returns HTTP 401 (not 404 — no user enumeration)."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nobody@finsight-test.dev", "password": "any"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ Unknown email → 401 (no user enumeration — correct)")


# ============================================================================
# TIER 3 — TOKEN LIFECYCLE
# ============================================================================

class TestTokenLifecycle:
    """GET /users/me, POST /auth/refresh, POST /auth/logout."""

    def test_get_profile_authenticated(self):
        """GET /users/me returns full user profile for a logged-in user."""
        assert _state.free_session, "Run login tests first"
        r = _get(_state.free_session, "/users/me")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == FREE_EMAIL
        assert body["role"] == "free"
        assert "id" in body, "id field missing from /users/me response"
        assert "has_api_key" in body, "has_api_key field missing from /users/me response"
        assert body["has_api_key"] is False, "Free user should not have an API key"
        _state.free_user_id = body["id"]
        print(f"\n  ✓ GET /users/me — id={body['id']}, role={body['role']}, has_api_key={body['has_api_key']}")

    def test_get_profile_unauthenticated_returns_401(self):
        """GET /users/me without credentials returns 401."""
        r = requests.get(f"{BASE_URL}/users/me", timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ GET /users/me unauthenticated → 401 (correct)")

    def test_refresh_rotates_access_token(self):
        """POST /auth/refresh issues a new access_token cookie."""
        assert _state.free_session, "Run login tests first"
        old_token = _state.free_session.cookies.get("access_token")
        # Wait 1 second so the new token has a different iat claim.
        time.sleep(1)
        r = _post(_state.free_session, "/auth/refresh")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        new_token = _state.free_session.cookies.get("access_token")
        assert new_token, "access_token cookie not set after refresh"
        assert new_token != old_token, "access_token should be different after refresh"
        print(f"\n  ✓ Token refreshed (new token differs from old)")

    def test_refresh_without_cookie_returns_401(self):
        """POST /auth/refresh without a refresh_token cookie returns 401."""
        r = requests.post(f"{BASE_URL}/auth/refresh", timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ /auth/refresh without cookie → 401 (correct)")

    def test_logout_clears_cookies(self):
        """POST /auth/logout revokes the token and clears cookies."""
        # Use a fresh session to avoid interfering with the main test session.
        s = requests.Session()
        reg = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": LOGOUT_EMAIL},
            timeout=TIMEOUT,
        )
        if reg.status_code != 201:
            pytest.skip("Could not register test user for logout test")
        pwd = reg.json()["generated_password"]

        login_r = _post(s, "/auth/login", json={"email": LOGOUT_EMAIL, "password": pwd})
        assert login_r.status_code == 200
        assert "access_token" in s.cookies

        logout_r = _post(s, "/auth/logout")
        assert logout_r.status_code == 204, f"Expected 204, got {logout_r.status_code}"

        # The browser cookie jar should have the cookie cleared (empty value or absent).
        access_after = s.cookies.get("access_token")
        assert not access_after, f"Cookie should be cleared; got: {access_after!r}"
        print("\n  ✓ Logout OK — cookies cleared")

    def test_profile_after_logout_returns_401(self):
        """GET /users/me with no cookies returns 401."""
        r = requests.get(f"{BASE_URL}/users/me", timeout=TIMEOUT)
        assert r.status_code == 401
        print("\n  ✓ GET /users/me after logout (no cookies) → 401 (correct)")


# ============================================================================
# TIER 4 — RBAC GATES
# ============================================================================

class TestRBACGates:
    """Verify role-based access control on protected endpoints."""

    SEARCH_PAYLOAD = {"ticker": "MAYBANK", "statement_type": "kpi"}

    def test_public_endpoints_still_accessible(self):
        """Public company endpoints return 200 without any credentials."""
        for path in ["/companies", "/companies/MAYBANK", "/health"]:
            r = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
            assert r.status_code == 200, f"GET {path} expected 200, got {r.status_code}"
        print("\n  ✓ Public endpoints (GET /companies, /health) → 200 (correct)")

    def test_search_unauthenticated_returns_401(self):
        """POST /search without credentials returns 401."""
        r = requests.post(f"{BASE_URL}/search", json=self.SEARCH_PAYLOAD, timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ POST /search unauthenticated → 401 (correct)")

    def test_search_free_session_returns_403(self):
        """POST /search with a free-tier session returns 403 (not paid/admin)."""
        assert _state.free_session, "Run login tests first"
        r = _post(_state.free_session, "/search", json=self.SEARCH_PAYLOAD)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("\n  ✓ POST /search with free session → 403 (correct)")

    def test_search_bad_api_key_returns_401(self):
        """POST /search with an invalid X-API-Key header returns 401."""
        r = requests.post(
            f"{BASE_URL}/search",
            json=self.SEARCH_PAYLOAD,
            headers={"X-API-Key": "fsk_not_a_real_key"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ POST /search with invalid API key → 401 (correct)")

    def test_admin_users_free_session_returns_403(self):
        """GET /admin/users with a free session returns 403."""
        assert _state.free_session, "Run login tests first"
        r = _get(_state.free_session, "/admin/users")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("\n  ✓ GET /admin/users with free session → 403 (correct)")

    def test_api_key_endpoint_free_session_returns_403(self):
        """GET /users/me/api-key with a free session returns 403."""
        assert _state.free_session, "Run login tests first"
        r = _get(_state.free_session, "/users/me/api-key")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("\n  ✓ GET /users/me/api-key with free session → 403 (correct)")

    def test_api_key_rotate_free_session_returns_403(self):
        """POST /users/me/api-key/rotate with a free session returns 403."""
        assert _state.free_session, "Run login tests first"
        r = _post(_state.free_session, "/users/me/api-key/rotate")
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("\n  ✓ POST /users/me/api-key/rotate with free session → 403 (correct)")


# ============================================================================
# TIER 5 — BFF ROUTES (requires Next.js dev server)
# ============================================================================

@pytest.mark.skipif(not _HAS_BFF, reason="Set FINSIGHT_FRONTEND_URL to run BFF tests")
class TestBFFRoutes:
    """
    Verify the Next.js BFF proxy routes (/api/auth/**, /api/users/**).

    These tests confirm that:
    1. The BFF correctly proxies requests to FastAPI.
    2. Cookies set by FastAPI are relayed to the browser.
    3. POST /api/auth/login returns a full AuthUser shape
       ({id, email, role, has_api_key}) not just the bare FastAPI response.
    4. The BFF enforces auth on admin routes.
    """

    _bff_session: requests.Session | None = None
    _bff_email: str = f"test_bff_{_RUN_ID}@finsight-test.dev"
    _bff_password: str = ""

    @classmethod
    def _setup_bff_account(cls):
        """Register and log in via the BFF; cache the session."""
        if cls._bff_session:
            return cls._bff_session

        # Register via FastAPI directly (BFF register just proxies).
        reg = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": cls._bff_email},
            timeout=TIMEOUT,
        )
        if reg.status_code != 201:
            pytest.skip(f"Could not register BFF test user: {reg.text}")
        cls._bff_password = reg.json()["generated_password"]

        # Log in via the BFF.
        s = requests.Session()
        login = s.post(
            f"{FRONTEND_URL}/api/auth/login",
            json={"email": cls._bff_email, "password": cls._bff_password},
            timeout=TIMEOUT,
        )
        if login.status_code != 200:
            pytest.skip(f"BFF login failed: {login.status_code} {login.text}")
        cls._bff_session = s
        return s

    def test_bff_register_returns_generated_password(self):
        """POST /api/auth/register proxies correctly and returns generated_password."""
        unique = f"test_bff_reg_{_RUN_ID}@finsight-test.dev"
        r = requests.post(
            f"{FRONTEND_URL}/api/auth/register",
            json={"email": unique},
            timeout=TIMEOUT,
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert "generated_password" in body, "generated_password missing from BFF register response"
        assert body["email"] == unique
        print(f"\n  ✓ BFF POST /api/auth/register → 201, generated_password present")

    def test_bff_login_returns_full_auth_user(self):
        """
        POST /api/auth/login must return the full AuthUser shape:
        {id, email, role, has_api_key}.

        The bare FastAPI login response only returns {email, role, message}.
        The login BFF was fixed to call /users/me and return the complete shape.
        """
        s = self._setup_bff_account()
        login_body = s.post(
            f"{FRONTEND_URL}/api/auth/login",
            json={"email": self._bff_email, "password": self._bff_password},
            timeout=TIMEOUT,
        )
        assert login_body.status_code == 200, f"BFF login failed: {login_body.text}"
        body = login_body.json()

        # Full AuthUser shape must be present:
        assert "id" in body, "id missing — BFF login returns incomplete AuthUser shape"
        assert "email" in body, "email missing"
        assert "role" in body, "role missing"
        assert "has_api_key" in body, "has_api_key missing — BFF login returns incomplete shape"
        assert body["email"] == self._bff_email
        assert body["role"] == "free"
        assert isinstance(body["id"], int) and body["id"] > 0, "id must be a positive integer"
        assert body["has_api_key"] is False
        print(f"\n  ✓ BFF login returns full AuthUser: id={body['id']}, has_api_key={body['has_api_key']}")

    def test_bff_login_sets_cookies(self):
        """POST /api/auth/login relays HttpOnly cookies from FastAPI to the browser."""
        s = self._setup_bff_account()
        assert "access_token" in s.cookies, "access_token cookie missing after BFF login"
        assert "refresh_token" in s.cookies, "refresh_token cookie missing after BFF login"
        print("\n  ✓ BFF login sets access_token + refresh_token cookies")

    def test_bff_me_returns_user_profile(self):
        """GET /api/auth/me returns the authenticated user's profile."""
        s = self._setup_bff_account()
        r = s.get(f"{FRONTEND_URL}/api/auth/me", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["email"] == self._bff_email
        assert body["role"] == "free"
        print(f"\n  ✓ BFF GET /api/auth/me → {body['email']} (role={body['role']})")

    def test_bff_me_unauthenticated_returns_401(self):
        """GET /api/auth/me without session returns 401."""
        r = requests.get(f"{FRONTEND_URL}/api/auth/me", timeout=TIMEOUT)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ BFF GET /api/auth/me (no cookie) → 401 (correct)")

    def test_bff_logout_clears_cookies(self):
        """POST /api/auth/logout relays the cookie-clearing Set-Cookie headers."""
        s = self._setup_bff_account()
        r = s.post(f"{FRONTEND_URL}/api/auth/logout", timeout=TIMEOUT)
        # 200 or 204 are both acceptable depending on BFF implementation.
        assert r.status_code in (200, 204), f"Expected 200/204, got {r.status_code}: {r.text}"
        access_after = s.cookies.get("access_token")
        assert not access_after, f"Cookie should be cleared; got: {access_after!r}"
        print("\n  ✓ BFF POST /api/auth/logout → cookies cleared")

    def test_bff_admin_users_unauthenticated_returns_401_or_403(self):
        """GET /api/admin/users without session returns 401 or 403."""
        r = requests.get(f"{FRONTEND_URL}/api/admin/users", timeout=TIMEOUT)
        assert r.status_code in (401, 403), (
            f"Expected 401 or 403, got {r.status_code}: {r.text}"
        )
        print(f"\n  ✓ BFF GET /api/admin/users unauthenticated → {r.status_code}")

    def test_bff_login_wrong_password_returns_401(self):
        """POST /api/auth/login with wrong password returns 401."""
        r = requests.post(
            f"{FRONTEND_URL}/api/auth/login",
            json={"email": self._bff_email, "password": "wrong_password"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ BFF login wrong password → 401 (correct)")


# ============================================================================
# TIER 6 — ADMIN FLOW
# ============================================================================

@pytest.mark.skipif(
    not _HAS_ADMIN,
    reason="Set FINSIGHT_ADMIN_EMAIL + FINSIGHT_ADMIN_PASSWORD to run admin tests",
)
class TestAdminFlow:
    """Admin user management: list, upgrade role, deactivate, delete."""

    _admin_session: requests.Session | None = None

    @classmethod
    def _login_as_admin(cls) -> requests.Session:
        if cls._admin_session:
            return cls._admin_session
        s = requests.Session()
        r = s.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, timeout=TIMEOUT)
        assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
        assert r.json()["role"] == "admin", "FINSIGHT_ADMIN_EMAIL is not an admin account"
        cls._admin_session = s
        return s

    def test_admin_can_login(self):
        """Admin login succeeds and returns role='admin'."""
        s = self._login_as_admin()
        r = _get(s, "/users/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"
        print(f"\n  ✓ Admin logged in: {ADMIN_EMAIL}")

    def test_admin_list_users(self):
        """GET /admin/users returns paginated user list."""
        s = self._login_as_admin()
        r = _get(s, "/admin/users?page=1&page_size=10")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert "users" in body and "total" in body
        assert isinstance(body["users"], list)
        print(f"\n  ✓ Admin sees {body['total']} user(s), page has {len(body['users'])} rows")

    def test_admin_can_register_and_upgrade_user(self):
        """Admin can upgrade a free user to 'paid' via PATCH /admin/users/{id}."""
        assert _state.free_user_id, "Run token lifecycle tests first"
        s = self._login_as_admin()
        r = _patch(s, f"/admin/users/{_state.free_user_id}", json={"role": "paid"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body["role"] == "paid"
        print(f"\n  ✓ Admin upgraded user {_state.free_user_id} → paid")

    def test_upgraded_user_can_generate_api_key(self):
        """After upgrade to 'paid', the user can generate an API key."""
        assert _state.free_session, "No free session"
        # Refresh the access token so it carries the new 'paid' role.
        r = _post(_state.free_session, "/auth/refresh")
        assert r.status_code == 200, f"Token refresh failed: {r.status_code} {r.text}"

        r = _post(_state.free_session, "/users/me/api-key/rotate")
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        body = r.json()
        assert "raw_key" in body and body["raw_key"].startswith("fsk_")
        _state.api_key_raw = body["raw_key"]
        print(f"\n  ✓ API key generated: {body['raw_key'][:12]}… (prefix: {body['key_prefix']})")

    def test_api_key_allows_search(self):
        """A valid API key grants access to POST /search."""
        assert _state.api_key_raw, "Run API key generation test first"
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
        assert "data" in body and "revenue_bln" in body["data"]
        print(f"\n  ✓ API key search: ticker={body['ticker']}, fy={body['fiscal_year']}")

    def test_paid_session_cookie_allows_search(self):
        """A 'paid' session cookie also grants access to POST /search."""
        assert _state.free_session, "No session"
        r = _post(
            _state.free_session,
            "/search",
            json={"ticker": "CIMB", "statement_type": "income_statement"},
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        print("\n  ✓ Paid session cookie /search → 200")

    def test_admin_deactivate_user(self):
        """Admin can deactivate a user account."""
        assert _state.free_user_id
        s = self._login_as_admin()
        r = _patch(s, f"/admin/users/{_state.free_user_id}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        print(f"\n  ✓ User {_state.free_user_id} deactivated")

    def test_deactivated_user_cannot_login(self):
        """A deactivated account cannot log in."""
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": FREE_EMAIL, "password": _state.generated_password},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("\n  ✓ Deactivated user login → 401 (correct)")

    def test_admin_delete_test_user(self):
        """Admin can permanently delete a user account."""
        assert _state.free_user_id
        s = self._login_as_admin()
        r = _delete(s, f"/admin/users/{_state.free_user_id}")
        assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"
        print(f"\n  ✓ User {_state.free_user_id} deleted")

    def test_deleted_user_not_in_list(self):
        """Deleted user no longer appears in the admin user list."""
        s = self._login_as_admin()
        r = _get(s, "/admin/users?page=1&page_size=100")
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()["users"]]
        assert _state.free_user_id not in ids
        print(f"\n  ✓ Deleted user {_state.free_user_id} absent from user list")

    def test_admin_invalid_role_returns_422(self):
        """PATCH /admin/users/{id} with an invalid role returns 422."""
        # Register a fresh user to target.
        reg = requests.post(
            f"{BASE_URL}/auth/register",
            json={"email": ADMIN_DELETE_EMAIL},
            timeout=TIMEOUT,
        )
        if reg.status_code != 201:
            pytest.skip("Could not register helper user")
        uid = None
        s = self._login_as_admin()
        users_r = _get(s, "/admin/users?page=1&page_size=100")
        for u in users_r.json()["users"]:
            if u["email"] == ADMIN_DELETE_EMAIL:
                uid = u["id"]
                break
        if not uid:
            pytest.skip("Could not find helper user in list")

        r = _patch(s, f"/admin/users/{uid}", json={"role": "superuser"})
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
        print("\n  ✓ Invalid role value → 422 (correct)")

        # Clean up.
        _delete(s, f"/admin/users/{uid}")


# ============================================================================
# TIER 7 — WEBHOOK SECURITY
# ============================================================================

class TestWebhookSecurity:
    """Stripe webhook signature verification."""

    def test_webhook_invalid_signature_returns_400_or_500(self):
        """POST /webhooks/stripe with an invalid signature is rejected."""
        r = requests.post(
            f"{BASE_URL}/webhooks/stripe",
            data=b'{"type": "invoice.payment_succeeded", "data": {"object": {}}}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=12345,v1=invalid_signature",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 500), (
            f"Expected 400 or 500, got {r.status_code}: {r.text}"
        )
        print(f"\n  ✓ Webhook invalid signature → {r.status_code} (rejected correctly)")

    def test_webhook_no_signature_returns_400_or_500(self):
        """POST /webhooks/stripe without a Stripe-Signature header is rejected."""
        r = requests.post(
            f"{BASE_URL}/webhooks/stripe",
            data=b'{"type": "test"}',
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 500), (
            f"Expected 400 or 500, got {r.status_code}: {r.text}"
        )
        print(f"\n  ✓ Webhook no signature → {r.status_code} (rejected correctly)")


# ============================================================================
# Standalone runner — human-readable walkthrough
# ============================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  FinSight Phase 4 — Full-Stack Integration Test")
    print("=" * 65)
    print(f"  Backend:  {BASE_URL}")
    print(f"  Frontend: {FRONTEND_URL or '(not set — BFF tests skipped)'}")
    print(f"  Run ID:   {_RUN_ID}")
    if not _HAS_ADMIN:
        print("\n  ⚠  Admin tests SKIPPED (set FINSIGHT_ADMIN_EMAIL + FINSIGHT_ADMIN_PASSWORD)")
    if not _HAS_BFF:
        print("  ⚠  BFF tests SKIPPED (set FINSIGHT_FRONTEND_URL=http://localhost:3000)")

    ok, reason = _backend_available()
    if not ok:
        print(f"\n  ✗ Backend unreachable: {reason}")
        sys.exit(1)
    print(f"\n  ✓ Backend reachable\n")

    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
