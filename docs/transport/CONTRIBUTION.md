# Sarthak's transport and farmer-pooling contribution

Contributor: **Sarthak Kaushik — [@TheSarthak08](https://github.com/TheSarthak08)**

Review branch: **`sarthak/transport-pooling-portal`**

Prepared: **2026-09-16**

Integration status: **proposed on a feature branch; not merged into `main`**

## What this contribution implements

- Deterministic Python whole-vehicle selection and exact, quantity-proportional shares.
- FastAPI routes, validated inputs, versioned SQLAlchemy models and Alembic migrations.
- Persistent pools with join approval, withdrawal, capacity checks, lock, dispatch,
  settlement/cancellation records and audit events. Produce remains separately identified.
- A calculator with 1–12 named vehicle types, add/remove controls and worked costs.
- A separate farmer portal with password registration/sign-in, trip discovery, own-trip
  history, organizer approval, each farmer's cost share and approved-member group chat.
- Windows launchers, automated tests and a GitHub Actions workflow with PostgreSQL.

## Code ownership map for reviewers

| Area | File or folder |
| --- | --- |
| Pure transport arithmetic | `backend/src/mandiwise_transport/engine.py` |
| Persistence and input validation | `db.py`, `schemas.py`, `backend/migrations/` |
| Lifecycle and access rules | `services.py`, `api.py` |
| Portal authentication, discovery and chat | `portal.py` |
| Calculator API and local launcher | `presentation.py` |
| Browser interface | `backend/src/mandiwise_transport/web/` |
| Automated verification | `backend/tests/` |
| Developer/demo documentation | `backend/README.md`, `docs/transport/` |

Bare Python filenames above are relative to `backend/src/mandiwise_transport/`.
Existing datasets, ingestion scripts, research and the team's decision log are preserved.
This contribution does not claim ownership of the original project or the team's work.

## How teammates can review

After the branch is published, fetch it and check it out in a clean working directory:

```sh
git fetch origin
git switch --track origin/sarthak/transport-pooling-portal
cd backend
uv sync --frozen --extra test
uv run ruff check src tests scripts migrations
uv run pytest -q
uv run python -m mandiwise_transport.presentation
```

Use a virtual environment and `python -m pip install -e ".[test]"` if not using uv.
For an existing full API database, back it up and run `alembic upgrade head` before
starting the new code. No existing developer database is included in this branch.

Review checklist:

- Reproduce the default two-farmer estimate: 80 q, 60 km, Rs 3700 total, Rs 1850 each.
- Add/remove a vehicle type and verify the changed quote.
- Create two separate accounts and complete post → join → approve → chat → lock.
- Verify other farmers cannot approve requests or read an unapproved group's chat.
- Check the migrations and PostgreSQL CI before deciding whether to merge.
- Review the provisional policies below with the group; do not treat them as agreed
  project-wide decisions. Merge only after the team approves; no automatic merge is set.

## Integration boundaries and limitations

The `transport_` tables and temporary user records isolate this contribution from the
future shared project schema. Portal registration grants the ability to organize one's
own trips, never admin catalogue permissions. Replace that temporary onboarding with
the team's agreed identity system during integration.

The browser UI is a plain HTML/CSS/JavaScript classroom client, **not** the planned
React/Vite multilingual app. It is English-only. The prototype does not complete the
team's i18n, production authentication, mapping, ingestion or mandi-ranking tasks.

Distances and supplier prices must be entered/verified manually. Market datasets do
not supply vehicle prices. Vehicle availability is assumed, not checked. The prototype
does not book transport, collect money, verify identities or calculate crop-sale profit.
Locking refuses a proportional split that makes any farmer worse off than travelling
alone; this is a provisional policy for team review.

Chat updates require refresh. Account recovery, session revocation, identity verification,
moderation, HTTPS deployment, shared throttling and backup operations are not implemented.
See [development notes](DEVELOPMENT.md) before exposing this to real users.
