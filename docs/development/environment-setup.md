# Environment Setup

!!! success "Phase 4 Live"
    Phase 4 adds JWT auth, RBAC, Stripe, and Alembic migrations.
    Follow the Phase 4 sections below for the correct local dev configuration.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.12 | Backend and data pipeline |
| Node.js | ≥ 20 | Next.js frontend |
| Docker Desktop | Latest | PostgreSQL (optional — can use local Postgres) |
| uv | Latest | Fast Python package management |
| Git | Latest | Version control |

---

## Clone the Repository

```bash
git clone https://github.com/ONGKOKRHUI/financial-insights.git
cd financial-insights
```

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

!!! warning "Critical settings for local development (without Docker)"
    The defaults in `.env.example` are tuned for **Docker Compose**.
    For plain local development (`uvicorn` + `npm run dev`) you **must**
    change two values in your `.env`:

    | Variable | Docker Compose value | Plain local value |
    |---|---|---|
    | `INTERNAL_API_URL` | `http://backend:8000` | `http://localhost:8000` |
    | `COOKIE_SECURE` | _(not set — defaults true)_ | `false` |

    Without `COOKIE_SECURE=false`, the backend sets the `Secure` flag on
    cookies which requires HTTPS.  On plain `http://localhost` the browser
    silently discards those cookies, causing all logins to fail with 401
    despite appearing to succeed.

### Minimum required variables

```bash
# Backend (src/backend/.env or set in shell)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/finsight
SECRET_KEY=<openssl rand -hex 32>
COOKIE_SECURE=false          # local dev only
ALLOWED_ORIGINS=http://localhost:3000

# Frontend (frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
INTERNAL_API_URL=http://localhost:8000   # must NOT be http://backend:8000

# Phase 4 Stripe (optional for local — returns 503 if omitted)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRO_PRICE_ID=price_...
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## Backend Setup

```bash
# Install dependencies
cd src/backend
uv sync      # or: pip install -r requirements.txt

# Apply Alembic migrations (creates users, refresh_tokens, api_keys tables)
alembic upgrade head

# Seed demo data and start the server
uvicorn main:app --reload --port 8000
```

Verify the backend is running:

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

---

## Frontend Setup

```bash
cd frontend
npm install

# Create a local env file for Next.js
cp .env.example .env.local
# Edit .env.local: set INTERNAL_API_URL=http://localhost:8000

npm run dev
# → http://localhost:3000
```

---

## Create an Admin Account

After both servers are running:

1. Register normally via the UI at `http://localhost:3000/auth/register`.
2. Copy the generated password shown in the modal.
3. Manually promote the account to `admin` in the database:

```bash
# Using psql
psql $DATABASE_URL -c "UPDATE users SET role='admin' WHERE email='your@email.com';"
```

4. Store the credentials for running admin integration tests:

```bash
export FINSIGHT_ADMIN_EMAIL=your@email.com
export FINSIGHT_ADMIN_PASSWORD=<copied_generated_password>
```

---

## Run Integration Tests

```bash
# Backend tests only (against local backend)
FINSIGHT_BASE_URL=http://localhost:8000 \
  pytest tests/test_phase4_full_stack.py -v

# Full-stack tests (backend + BFF routes, requires both servers running)
FINSIGHT_BASE_URL=http://localhost:8000 \
FINSIGHT_FRONTEND_URL=http://localhost:3000 \
  pytest tests/test_phase4_full_stack.py -v

# With admin tests enabled
FINSIGHT_BASE_URL=http://localhost:8000 \
FINSIGHT_FRONTEND_URL=http://localhost:3000 \
FINSIGHT_ADMIN_EMAIL=admin@example.com \
FINSIGHT_ADMIN_PASSWORD=<password> \
  pytest tests/test_phase4_full_stack.py -v
```

---

## Production Deployment Variables

### Render (FastAPI backend)

| Variable | Value |
|---|---|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app,http://localhost:3000` |
| `COOKIE_SECURE` | _(leave unset — defaults to `true`)_ |
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |

### Vercel (Next.js frontend)

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://finsight-api.onrender.com` |
| `INTERNAL_API_URL` | `https://finsight-api.onrender.com` |
| `STRIPE_SECRET_KEY` | `sk_live_...` (BFF checkout route) |
| `STRIPE_PRO_PRICE_ID` | `price_...` |
| `NEXT_PUBLIC_APP_URL` | `https://your-app.vercel.app` |

!!! danger "INTERNAL_API_URL on Vercel"
    You **must** set `INTERNAL_API_URL` to the Render backend URL in the
    Vercel dashboard.  Without this, all Next.js BFF route handlers
    (login, register, /users/me, etc.) will attempt to reach
    `http://backend:8000` (the Docker Compose hostname) which is
    unreachable from Vercel, causing 502 errors on every auth action.
