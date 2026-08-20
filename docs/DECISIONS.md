# Decisions

This is an append-only decision log. Each entry has a date, the decision, and why it was made. Entries are never edited or deleted. Superseding a decision means adding a new entry that says so and points back to the one it replaces — the old entry stays as-is.

Format: `Date | Decision | Why`

---

- **2026-08-20** — Named the project MandiWise. *Why:* clear, descriptive name for a tool that helps farmers make smarter mandi choices.
- **2026-08-20** — Three roles only: Farmer, Pool Coordinator, Admin. *Why:* keeps the permission model simple for a first build with no confirmed need for more.
- **2026-08-20** — Pool Coordinator is a permission on a farmer account, not a separate user type. *Why:* avoids duplicating farmer identity/data for someone who is still a farmer, just also organizing a pool.
- **2026-08-20** — No price forecasting. *Why:* out of scope; forecasting accuracy is unverified and the core net-realisation claim itself hasn't been validated yet.
- **2026-08-20** — Arrivals volume dropped from scope. *Why:* would require scraping AGMARKNET, which isn't part of the current official data feed.
- **2026-08-20** — No payments, trading, or credit features. *Why:* out of scope for a price/pooling advisory tool; avoids financial liability and regulatory surface.
- **2026-08-20** — The government API is called on a schedule, never in the request path. *Why:* per working rules — keeps the app responsive and doesn't depend on upstream API availability at request time.
- **2026-08-20** — Pooling covers shared transport, not produce; each farmer's lot stays identity-preserved. *Why:* farmers keep ownership and traceability of their own produce even when sharing a vehicle.
- **2026-08-20** — Pool cost splits by quantity, not sale value. *Why:* simpler to compute and verify, and avoids disputes over what each farmer's produce is "worth."
- **2026-08-20** — The platform does not adjudicate quality disputes. *Why:* out of scope; no mechanism to verify produce quality claims, and it creates liability the platform can't back up.
- **2026-08-20** — Liquidity signal is derived from reporting frequency. *Why:* consistent price reporting for a mandi/commodity is a usable proxy for an active, reliable market — see the liquidity hedge in claude.md.
- **2026-08-20** — Rates (commission, cess, handling, transport) live in DB config tables with a source and effective date, never hardcoded. *Why:* per working rules — rates are data, not code, and must stay traceable to a source.
- **2026-08-20** — Distance between mandis comes from a precomputed matrix, with haversine as a fallback. *Why:* avoids live geocoding/routing API calls in the request path and keeps distance lookups fast and free.
- **2026-08-20** — i18n is wired in from the first commit. *Why:* retrofitting internationalization later is expensive; the target users need this from day one.
- **2026-08-20** — Multilingual UI is a requirement, not a differentiator. *Why:* the primary users are farmers who need the product in their own language to use it at all.
