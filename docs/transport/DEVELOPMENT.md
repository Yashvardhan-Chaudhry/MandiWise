# Farmer pooling: implementation and deployment notes

The calculator remains `/demo`, with a reusable 1–12 type vehicle editor. The separate
`/pooling` UI uses saved pools and the existing exact transport engine, not mock matches.

## Data and authorization

- Migration `0002` adds `transport_portal_accounts` and `transport_portal_messages`.
  Run `alembic upgrade head` against an existing full-backend database before use.
- Local `presentation` launcher creates its own `portal.db` automatically. Do not use
  `create_all` as a migration strategy for deployed databases.
- Registration assigns coordinator permission so farmers can organize their own groups;
  it never permits administrative catalogue writes. Each trip's organizer alone can
  approve members or change lifecycle state. Portal trip creation accepts farmer or
  coordinator accounts and creates immutable, organizer-entered route/rate snapshots.
- Passwords use salted scrypt (N=32768, r=8, p=3), never plaintext. New passwords require
  15–128 characters. Sign-in uses a 12-hour HttpOnly SameSite=Strict cookie, Secure over
  HTTPS. No access token is placed in browser storage. Cookie-auth writes require a
  custom header and reject a mismatched Origin. Existing bearer clients still work.
- The local launcher generates a fresh signing secret per run unless JWT_SECRET is set;
  records survive restart but sessions must sign in again. Logout clears the browser
  cookie; this prototype does not implement server-side JWT revocation or recovery.
- Chat checks membership on every request. Only the organizer and approved members have
  access; cancelled/settled trips are read-only. The UI uses textContent for user text.
- Public discovery is explicit: self-declared organizer names, trip details, aggregate
  load and entered rates. Personal lot declarations and financial shares are restricted.

## Limits and deployment gates

This is a tested local project prototype, not production-ready public onboarding.
Auth throttling is in-process/IP based and resets on restart; a shared rate-limit store
and properly configured proxy/IP trust are needed for deployment. Add HTTPS, verified
identities, password recovery, session revocation, abuse reporting/moderation, backups
and monitoring before inviting public users. There is no phone verification, map route
calculation, automated driver dispatch, payment processing or real-time message push.

Discovery pages contain up to 30 trips with Load more. My trips shows the latest 100.
Chat shows the latest 100 messages; updates require Refresh chat. Vehicle counts assume
unbounded availability, as in the existing engine. Organizer-entered rates must be
confirmed with a transporter; quantities/lot compatibility are organizer-reviewed.

## Verification

Run `python -m pytest -q`. Portal tests cover two separate authenticated farmers,
discovery, join/approval, unauthorized review/chat, own-share privacy, withdrawal,
locking, persistence after application restart, password hashing, cookie CSRF checks,
validation, no admin escalation and custom vehicle quotes. Migration metadata is
checked against the models. PostgreSQL integration remains optional via TEST_POSTGRES_URL.
