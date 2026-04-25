# Authentication

!!! success "Phase 4 — JWT + API Key Auth"
    Authentication is fully implemented in Phase 4.  All token exchange
    uses HttpOnly cookies for the web dashboard and an ``X-API-Key`` header
    for programmatic API access.

---

## Overview

FinSight uses two parallel authentication mechanisms:

| Mechanism | Used by | Transport |
|---|---|---|
| **JWT (HttpOnly cookies)** | Web dashboard (browser) | `Set-Cookie` header — never JavaScript-readable |
| **API Key (`X-API-Key`)** | Programmatic clients, scripts | Request header |

Both mechanisms are enforced server-side by FastAPI dependencies on every
protected route.  The middleware in `middleware.ts` is a UX-level guard
only — the real security boundary is always the backend.

---

## JWT Cookie Authentication

### Registration

`POST /auth/register` — accepts an email address only.  The server generates
a cryptographically secure password (`secrets.token_urlsafe`) and returns it
**once** in the response body.

```bash
curl -s -X POST https://finsight-api.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com"}' | jq .
```

```json
{
  "email": "dev@example.com",
  "generated_password": "K7hXqN2-Rv8pzYoLmTcAeD",
  "message": "Account created. Copy your password now — it will not be shown again."
}
```

!!! warning "One-time password"
    Store the generated password immediately — it is not recoverable.

### Login

`POST /auth/login` — exchange credentials for two HttpOnly cookies:

| Cookie | TTL | Contents |
|---|---|---|
| `access_token` | 15 minutes | JWT with `sub`, `role`, `exp`, `type: "access"` |
| `refresh_token` | 7 days | JWT with `sub`, `exp`, `type: "refresh"` |

```bash
curl -s -c cookies.txt -X POST https://finsight-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "K7hXqN2-Rv8pzYoLmTcAeD"}'
```

Cookie security attributes:

```
Set-Cookie: access_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=900
Set-Cookie: refresh_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800
```

- **`HttpOnly`** — JavaScript cannot read these cookies (XSS protection).
- **`Secure`** — transmitted over HTTPS only.
- **`SameSite=Lax`** — blocks cross-site POST forgery while allowing top-level navigations.

### Token Refresh

`POST /auth/refresh` — rotate the access token using the refresh cookie.
The refresh token hash is verified against the database on every call so
it can be revoked server-side.

```bash
curl -s -b cookies.txt -c cookies.txt -X POST \
  https://finsight-api.onrender.com/auth/refresh
```

### Logout

`POST /auth/logout` — revokes the refresh token in the database and clears
both cookies by setting `Max-Age=0`.

```bash
curl -s -b cookies.txt -X POST https://finsight-api.onrender.com/auth/logout
```

---

## API Key Authentication

Developer API keys are available to `paid` and `admin` tier users.  A key
is automatically generated when a Stripe subscription payment succeeds.

### Usage

Pass the key in the `X-API-Key` request header:

```bash
curl -s -H "X-API-Key: fsk_yourKeyHere" \
  -X POST https://finsight-api.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"ticker": "MAYBANK", "statement_type": "kpi"}'
```

```python
import httpx

res = httpx.post(
    "https://finsight-api.onrender.com/search",
    json={"ticker": "MAYBANK", "statement_type": "income_statement"},
    headers={"X-API-Key": "fsk_yourKeyHere"},
)
print(res.json())
```

### Key Security

- Keys are prefixed `fsk_` for easy identification in environment files.
- Only the **SHA-256 hash** of the key is stored in the database — a breach
  does not expose live keys.
- A key is returned **exactly once** (at creation / rotation) and never
  retrievable again.
- Rotate immediately if accidentally exposed: `POST /users/me/api-key/rotate`.

---

## RBAC & Route Protection

| Endpoint | Unauthenticated | Free | Paid | Admin |
|---|:---:|:---:|:---:|:---:|
| `GET /companies/**` | ✅ | ✅ | ✅ | ✅ |
| `GET /financials/**` | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/**` | ✅ | ✅ | ✅ | ✅ |
| `GET /users/me` | ❌ | ✅ | ✅ | ✅ |
| `POST /search` | ❌ | ❌ | ✅ | ✅ |
| `GET /users/me/api-key` | ❌ | ❌ | ✅ | ✅ |
| `GET /admin/users` | ❌ | ❌ | ❌ | ✅ |

---

## Environment Variables

The following variables must be set on the backend (Render):

| Variable | Description |
|---|---|
| `SECRET_KEY` | 32-byte hex string for JWT signing (`openssl rand -hex 32`) |
| `ALGORITHM` | JWT algorithm (default: `HS256`) |
| `STRIPE_SECRET_KEY` | Stripe secret key (`sk_live_…` or `sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret from the Stripe dashboard |

Frontend (Vercel):

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Same Stripe secret key (used by BFF checkout route) |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for the MYR 29/mo subscription |
| `NEXT_PUBLIC_APP_URL` | Frontend base URL for Stripe success/cancel redirects |
