# Authentication

!!! success "Phase 3 — Open API"
    The FinSight API is currently **open**. No authentication header, API key,
    or token is required to call any endpoint. All requests are accepted as-is.

---

## Current State (Phase 3)

Send requests directly — no headers needed:

```bash
curl "https://finsight-api.onrender.com/companies/MAYBANK/summary"
```

```python
import httpx
res = httpx.get("https://finsight-api.onrender.com/companies/MAYBANK/summary")
print(res.json())
```

---

## Planned: API Key Authentication (Phase 4)

API key gating will be introduced in Phase 4 alongside the RBAC system. When
implemented:

- Keys will be passed via an `X-API-Key` request header.
- Free-tier keys will be rate-limited (10 req/min, 100 req/day).
- Paid-tier keys will have higher limits (300 req/min, 50,000 req/day).
- The endpoint paths and response shapes will **not change**.

Example of future usage (Phase 4+):

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
     "https://finsight-api.onrender.com/companies"
```

---

## Planned: JWT Session Auth (Phase 4)

The web dashboard will use OAuth2 + JWT (stored in HttpOnly cookies) for
session-based authentication and Role-Based Access Control (RBAC). This is
separate from the developer API key and applies only to the browser dashboard.

| Role        | Access Level                                            |
|-------------|---------------------------------------------------------|
| `anonymous` | Public landing page only                               |
| `free`      | Basic company metrics, limited API calls               |
| `paid`      | Full dashboard, deep analytics, unrestricted API       |
| `admin`     | All resources + user management                        |

---

## Security Guidance for Phase 4+

When API keys are introduced, treat them as secrets:

- Store in environment variables, never in source code.
- Use `NEXT_PUBLIC_` prefixes only for values intended to be public.
- Rotate keys immediately if accidentally exposed.
