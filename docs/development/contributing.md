# Contributing

---

## Branching Strategy

```
main          ← production-ready, protected
develop       ← integration branch
feature/*     ← new features (branch from develop)
fix/*         ← bug fixes
docs/*        ← documentation-only changes
```

---

## Development Workflow

1. Create a branch from `develop`:
   ```bash
   git checkout develop
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style guidelines below.

3. Write or update tests.

4. Open a pull request against `develop` with a clear description.

---

## Code Style

=== "Python"
    - Formatter: **Ruff** (`ruff format`)
    - Linter: **Ruff** (`ruff check`)
    - Type checking: **mypy** (strict mode)
    - Docstrings: Google style

=== "TypeScript"
    - Formatter: **Prettier**
    - Linter: **ESLint** (Next.js config)
    - Strict TypeScript: enabled

---

## Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hybrid search endpoint
fix: correct balance sheet null handling
docs: update API authentication guide
chore: upgrade fastapi to 0.115
```

---

## Pull Request Checklist

- [ ] Tests pass locally (`pytest` / `npm run lint` / `npm run build`)
- [ ] Linting passes (`ruff check` / `eslint`)
- [ ] Relevant documentation updated in `docs/`
- [ ] PR description explains the motivation
- [ ] No secrets or credentials committed

---

## Reporting Issues

<!-- Describe GitHub Issues workflow: bug report template, feature request template, discussion board -->

---

## Documentation Contributions

All documentation lives in `docs/`. To contribute:

```bash
mkdocs serve   # Preview changes at http://localhost:8000
```

Submit docs-only changes as a `docs/*` branch PR.
