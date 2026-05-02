## Create documentation site
- using Cursor, create the documentations .md files 
- created mkdocs.yml and deploy-docs-on-main.yml 
- install dependencies: pip install mkdocs-material mkdocs-minify-plugin
- serve locally from root: mkdocs serve 
- build the site locally: mkdocs build

## Create MVP main page
- using Cursor, create MVP landing page
- added VERCEL_TOKEN to github secrets
- npm install -g vercel
- vercel link -> create .vercel

## Deploy backend on render 
- look at src/backend/render.yaml
- auto redeploy when code pushed changes certain files: refer render.yaml
- deployed live on render: 
- link to swagger UI: https://financial-insights-grit.onrender.com
- deployed app on vercel: https://finsights-mauve.vercel.app/
- note: deployed successfully using vercel autodeploy but failed using github actions CI/CD

## PostgreSQL + Docker (Phase 2 MVP)

### Local development with Docker Compose
All three services (postgres, backend, frontend) run together via Docker Compose:
```bash
# From repo root — builds images and starts all services
docker compose up --build

# Frontend: http://localhost:3000
# Backend API + Swagger: http://localhost:8000/docs
# PostgreSQL: localhost:5432 (db: finsight, user: postgres, pass: postgres)
```

The backend seeds the database automatically on first startup (reads from `src/backend/data/mock_data.py`). No manual migration step is needed.

### Render deployment with managed PostgreSQL
- `src/backend/render.yaml` now declares a `finsight-db` PostgreSQL database (free plan)
- Render automatically sets `DATABASE_URL` env var on the web service; no manual config needed
- On first deploy after adding the DB, Render provisions the database then starts the backend which seeds it
- To provision: push the updated `render.yaml` to main and confirm the new database in the Render dashboard

### New API endpoints added
- `GET /financials/{ticker}/balance-sheet` — 5-year balance sheet history
- `GET /financials/{ticker}/cash-flow` — 5-year cash flow history
- `GET /companies/{ticker}/qualitative` — qualitative insights (outlook + key events)

### GitHub Actions workflow fixes
- `deploy-backend.yml` — paths corrected to `src/backend/**`; Python validation now runs from correct directory
- `deploy-frontend.yml` — type-check step now uses `working-directory: ./frontend`

### How to run locally
- cd src/backend
- Run `uvicorn main:app --reload --port 8000`
- in a new terminal
- cd frontend
- Run `npm run dev`
OR
- docker-compose up 
- docker-compose airflow ... up
- (follow the docs documentation page running instructions)