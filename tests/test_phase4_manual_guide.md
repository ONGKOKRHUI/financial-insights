---

## Summary of everything done

### Bugs found & fixed

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `src/backend/routers/auth.py` | `secure=True` cookie flag silently blocks all cookies on plain HTTP — root cause of login/registration failures locally | Added `COOKIE_SECURE` env var (default `"true"`); set it to `"false"` for local dev |
| 2 | `frontend/src/app/api/auth/login/route.ts` | Returns `{email, role, message}` from FastAPI, but `useLogin` stores it as `AuthUser` — `id` and `has_api_key` are `undefined` | After login, BFF now calls `/users/me` with the new token and returns the full `{id, email, role, has_api_key}` shape |
| 3 | `frontend/src/app/api/auth/login/route.ts` | No try-catch — backend unreachable causes an uncaught exception | Added try-catch returning 502 |
| 4 | `frontend/src/app/api/stripe/checkout/route.ts` | `throw new Error(...)` at module level — crashes Next.js route when `STRIPE_SECRET_KEY` is absent | Moved check and Stripe init inside the handler; returns 503 gracefully |
| 5 | `src/backend/routers/auth.py` | `/auth/refresh` re-reads role from DB (code comment added to clarify intent) | Comment added; existing code already correctly reads from DB |
| 6 | `.env.example` | `INTERNAL_API_URL=http://backend:8000` with no explanation causes 502 on non-Docker local dev; `ALLOWED_ORIGINS` missing Vercel URL | Updated example with clear annotations for both Docker and plain-local usage, added `COOKIE_SECURE=false` |

### New test file: `tests/test_phase4_full_stack.py`

7 test tiers covering: Registration · Login (cookies + full AuthUser shape) · Token lifecycle (refresh/logout) · RBAC gates (search, admin, API key) · BFF proxy routes (optional, activated by `FINSIGHT_FRONTEND_URL`) · Admin flow (upgrade, deactivate, delete) · Webhook signature security.

### Docs updated

- `docs/backend/authentication.md` — `COOKIE_SECURE` warning, BFF login explanation
- `docs/development/environment-setup.md` — full rewrite with Phase 4 setup, critical local dev warnings, production Vercel/Render variable tables, test run commands

---

## Step-by-step manual test guide

### Prerequisites — local

**1. Set environment variables.** In `.env` (or your shell) ensure:
```
COOKIE_SECURE=false
INTERNAL_API_URL=http://localhost:8000
ALLOWED_ORIGINS=http://localhost:3000
```

**2. Start the backend:**
```bash
cd src/backend && uvicorn main:app --reload --port 8000
curl http://localhost:8000/health  # should return {"status":"ok"}
```

**3. Start the frontend:**
```bash
cd frontend && npm run dev   # http://localhost:3000
```

---

### Test 1 — Unauthenticated access is blocked

Open `http://localhost:3000` — you should be **immediately redirected** to `/auth/login`. There is no marketing page.

---

### Test 2 — Registration

1. Go to `http://localhost:3000/auth/register`
2. Enter any email address, click **Create account**
3. A modal appears with a generated password (e.g. `xK9mNv…`). Click **Copy**, then **I've saved my password — go to login**
4. You land on `/auth/login`

**Expected:** 201 from backend, modal shown, redirected to login.

---

### Test 3 — Login and authenticated hub

1. Enter the email + copied password, click **Sign in**
2. You are redirected to `/` (the main hub)
3. The header shows your email, a **Free** badge, and a **Log Out** button
4. You see 8 company tiles, each with a locked analytics link and "Pro" badge
5. An **Unlock Pro Analytics** CTA appears below the grid

**Expected:** Login sets `access_token` + `refresh_token` cookies. Hub renders free-tier view.

---

### Test 4 — Free user access control

With a free session active:
- Navigate to `http://localhost:3000/dashboard/MAYBANK` → redirected to `/upgrade` (middleware)
- Navigate to `http://localhost:3000/admin/dashboard` → redirected to `/`
- Navigate to `http://localhost:3000/account` → shows account page with email + role badge

---

### Test 5 — Upgrade to paid (admin promotion)

1. Go to `/account` → note your numeric user ID from the profile
2. In psql: `UPDATE users SET role='paid' WHERE email='your@email.com';`
3. Log out (click **Log Out** in header)
4. Log in again
5. You now see company tiles as clickable deep-links to `/dashboard/[ticker]`
6. Click **MAYBANK** → opens `/dashboard/MAYBANK` with Sentiment Overlay, Radar, and Waterfall charts

---

### Test 6 — Admin dashboard

1. Promote your account to `admin`:
   `UPDATE users SET role='admin' WHERE email='your@email.com';`
2. Log out and log in again
3. Header shows an **Admin** link; hub shows an **Admin Dashboard →** button
4. Go to `/admin/dashboard` → paginated user table with role dropdowns and delete buttons

---

### Test 7 — Log out

Click **Log Out** in the header. You are redirected to `/auth/login`. Attempting to navigate to `/` redirects back to login.

---

### Automated tests

```bash
# Backend tiers only:
FINSIGHT_BASE_URL=http://localhost:8000 pytest tests/test_phase4_full_stack.py -v

# Full stack (includes BFF proxy verification):
FINSIGHT_BASE_URL=http://localhost:8000 \
FINSIGHT_FRONTEND_URL=http://localhost:3000 \
pytest tests/test_phase4_full_stack.py -v

# With admin tests:
FINSIGHT_BASE_URL=http://localhost:8000 \
FINSIGHT_FRONTEND_URL=http://localhost:3000 \
FINSIGHT_ADMIN_EMAIL=admin@example.com \
FINSIGHT_ADMIN_PASSWORD=<password> \
pytest tests/test_phase4_full_stack.py -v
```