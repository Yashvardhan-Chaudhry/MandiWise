# MandiWise React frontend

React + Vite, following ARCHITECTURE §3.1. Development contribution, not a production release. Original backend pages remain unchanged.

## Run on Windows

1. From the repository root, run `START_MANDIWISE.cmd` and leave the backend terminal open (port 8001).
2. Open another terminal in `frontend`, run `npm ci`, then `npm run dev`.
3. Open http://127.0.0.1:5173. Use this exact host, not localhost, for the development proxy's origin mapping.

Requires Node 20.19+ or 22.12+ compatible with Vite 7. Dependencies are pinned by package-lock.json. First installation needs network access.

Alternatively, after starting the backend, double-click `START_FRONTEND.cmd` at the repository root. It installs frontend dependencies on first use and opens the page.

## Connected features

- Overview and mobile navigation.
- Read-only historical Punjab market browser with crop/district/name filtering, dates, sources and reported min/modal/max values.
- Editable vehicle/farmer transport calculator calling the existing backend. No business arithmetic is duplicated in React.
- Cookie-based registration/sign-in/sign-out; no tokens saved to localStorage.
- Trip discovery, pagination, own trips, posting with caller-entered rates, joins, owner review, withdrawal, cost shares, lifecycle and approved-member chat.
- All public state changes use the existing backend permission/version checks. Server-side errors stay visible. Chat refresh is manual.
- Locale registry for 13 documented locales, Latin numerals, Urdu RTL direction, draft Hindi/Punjabi labels and explicit English fallbacks. No translation is claimed human-verified.

## Explicit gaps

This is NOT the complete promised product. Net-return ranking has no backend endpoint yet; the market browser does not call modal-price ordering a recommendation. No fresh feed, current liquidity signal, verified rates/distances, notifications, account recovery, automatic vehicle booking or payments are fabricated. Some explanatory labels and all raw crop/source names remain English pending translation review.

The price view imports the existing 7 September 2026 snapshot, not a copied/new dataset. Rows below the project's analysis floor or with invalid ordering are screened out in the display only. Raw data is untouched. Never present these as current prices.

The existing trip API has one district field for both endpoints. The new form explicitly asks for same-district trips until that API is extended. Punjab scope in the client is not a backend security restriction. Existing provenance and coordinator-role limitations remain; frontend checkboxes do not establish verified rates.

## Verify

`npm test` and `npm run build`.

Test two distinct accounts in separate browser sessions: post → request → approve → chat → quote → lock. Test a third account cannot approve/read chat, and verify reload preserves membership. Check rejection, withdrawal, cancellation and stale-version errors. Test narrow/mobile layouts and keyboard focus. The sign-in dialog uses native modal focus handling.

Vite's development/preview proxy maps only its exact local origins to the backend origin so cookie CSRF checks continue to reject foreign origins. For deployment, use a same-origin reverse proxy for `/portal/api`, `/v1`, `/demo/calculate` and `/health`; do not deploy this frontend alone and assume local API paths will exist. Production needs HTTPS, persistent storage, shared throttling and recovery/abuse controls. No deployment was performed.
