# Working together on MandiWise

Read `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` and `docs/TASKS.md` first. Coordinate
task claims with the team. Keep the decision log append-only; proposed choices in a
feature branch are not automatically team-approved decisions.

## Keep each contribution identifiable

Use a descriptive feature branch, for example
`transport-pooling-system`. Commit using an email associated with **your own**
GitHub account. GitHub Settings → Emails shows your private noreply address if needed.
Do not reuse another contributor's address.

Push the feature branch, then open a pull request against `main` for team review.
Describe the scope, setup, tests and known limitations. Do not force-push or merge
another person's work without coordination.

## Before requesting review

From `backend/`:

```sh
uv sync --frozen --extra test
uv run ruff check src tests scripts migrations
uv run pytest -q
```

The optional PostgreSQL test runs when TEST_POSTGRES_URL is set; CI supplies an isolated
PostgreSQL service. UI changes should also be checked in a browser. Keep migrations
consistent with database models and include templates/static assets in package data.

Never commit `.env`, credentials, local user databases, virtual environments, caches,
builds or generated ZIPs. Public source datasets already tracked by the project should
remain available; do not confuse them with private portal/account data.
