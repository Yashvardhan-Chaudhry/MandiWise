# Demo brief — read this before we present

Five-minute read. Purpose: **all three of us tell the same story and none of us claims something a
teammate's answer contradicts.** That, not a rough edge in the UI, is how a demo actually goes
wrong.

The demo script itself is `docs/DEMO_RUNBOOK.md`.

> **Update 2026-11-19 — read before reusing this brief.** It was written for the September demo.
> Three things changed on the 19th; the rest still stands.
> - **Tests:** 78 backend passed (+1 skipped) and 5 root, measured on PR #1; plus 6 frontend tests
>   on PR #2. Quote those once they merge, not "55".
> - **`net_realisation`:** rebuilt in the canonical engine, with the market-fee term and the min/max
>   range (PR #1). The fee *rate* is still an unsourced 0, so "net realisation is proven" stays on
>   the do-not-claim list.
> - **React client:** merged into `main` (PR #4): ranking screen, calculator, pooling and price
>   browsing, with 7 frontend tests. Its hi/pa strings are unverified. Say "built and connected to the
>   ranking API", never "multilingual UI finished".

---

## The one-sentence story

> We tested whether the idea was true before building on it. It is — 73.1% median price dispersion
> across 2,821 real cross-sections. The premise holds; the full product claim does not yet, and we
> can tell you exactly which piece is missing.

Everything below supports that sentence.

---

## Numbers that are safe to say

All measured, all reproducible from committed data, all in `research/findings.md`.

| Figure | Value | Where it comes from |
|---|---|---|
| Median price dispersion | **73.1%** | 2,821 same-day cross-sections |
| 25th percentile | 46.7% | same |
| Our own "strong" threshold | >10% | set in `claude.md` *before* we measured |
| Total rows analysed | 17,742 | 16,907 historical + 836 live = 17,743 on disk; 1 duplicate row dropped on load |
| Historical span | 2023-10-02 → 2025-10-30 | 7 Patiala mandis × 8 commodities |
| Rows carrying arrival volumes | 91.7% of historical rows | the live feed carries none |
| Liquidity | median 21 of 30 reporting days | but 40% of pairs intermittent or worse |
| Tests | 55 passing | 5 root + 50 backend (+1 skipped) |
| Engine benchmark | 0 cost disagreements in 3,000 trials | `research/engine_benchmark.md` |

**Do not round these upward, and do not quote a number that isn't on this list.** If you don't
remember one, say "it's in our findings document" — that is a perfectly good answer.

---

## Who owns what

**Yashvardhan — data pipeline and validation.**
Two pullers (`mandi_pull.py` for the live government feed, `ceda_pull.py` for two years of
history), the validation analysis, and the data-quality guards.
*Decision worth defending:* rejecting bad rows rather than cleaning them. One mandi published
placeholder prices of ₹0.08–₹32.90 on both live days we captured; we log and drop those rather than
silently averaging them in.
*Does not do:* run on a schedule yet. It's a manual command.

**Dhrity — recommendation engine (`src/mandiwise/`).**
Computes net realisation and ranks mandis: gross, minus commission, minus handling, minus
transport.
*Decision worth defending:* `Decimal` throughout, never floating point — money arithmetic that
doesn't drift. Validation on every input (commission must be within 0–1, quantity positive).
*Does not do:* the market fee (cess) term, or the min/max price range the architecture requires.
Both are written up as tasks. **Say so plainly if asked — it's already in `docs/TASKS.md`.**

**Sarthak — transport and pooling backend (`backend/`).**
FastAPI service, database schema and migrations, the vehicle-packing and cost-split engine, the
calculator page and the farmer pooling portal.
*Decision worth defending:* the pool lifecycle is enforced in code, not just hidden in the UI —
invalid state transitions are rejected server-side. A database constraint backs that up only as far
as the set of allowed state values; the transition rules themselves live in code.
Cost splits by quantity, never by sale value, so a farmer with premium produce doesn't subsidise
anyone.
*Does not do:* the Pool Coordinator is currently a separate user role rather than a permission on a
farmer account, which contradicts our own earlier decision. It's logged as a task.

---

## Hard questions, honest answers

**"Are these transport rates real?"**
No. They are explicitly labelled placeholders, and the program prints that warning every time it
runs. We chose not to invent plausible-looking numbers. Sourcing real local rates is our next step
and it's a phone call, not a coding problem.

**"So have you proven farmers make more money?"**
No — and that distinction matters. We've proven the **premise**: prices across nearby mandis do not
cluster, they differ by 73% at the median. The **product claim** is about net realisation after
real transport costs, and we can't prove that until the rates are sourced. We'd rather say that
than overstate it.

**"Why were there two engines doing the same thing?"**
Two of us solved the same problem independently, which we should have caught earlier. Rather than
argue about it, we benchmarked them against each other over 3,000 randomised cases: zero
disagreements on cost, so both were correct. We chose one on scaling behaviour and test coverage
and recorded the reasoning. The benchmark is in the repo.

**"What's your test coverage?"**
55 tests. Honestly, they're uneven: the backend is well covered, the root engine has one test file.
That gap is known and written down.

**"Show me the multilingual UI."**
Not built. We've decided the scope — 13 languages, with a policy that a language only ships once a
human has checked it — but the scaffolding is an open task. The current pages are English only.

**"Why is the README table different from what the demo printed?"**
Because the rate card changed and we flagged the old table rather than quietly deleting it. The
warning is at the top of that section.

**"What went wrong during the project?"**
Good question to answer confidently, not defensively. Real examples: the government API silently
drops any request whose user agent mentions Python — no error, it just hangs. A second data source
returns an empty result instead of an error when it throttles you, which looks exactly like "no
data exists" and briefly fooled us. About 30% of commodity names disagree between our two sources.
We found each of these by checking rather than assuming.

---

## Do not claim

Read this list. One person overclaiming is the main risk.

- ❌ That net realisation is proven. It is not.
- ❌ That the transport rates are real. They are placeholders.
- ❌ That the liquidity signal works on live data — we have 2 days of live data, which is not enough.
- ❌ That the multilingual UI is finished. The React client exists (merged 2026-11-19), but hi/pa text is unverified.
- ❌ That it runs on PostgreSQL. Everything you'll see runs on SQLite; Postgres is CI only.
- ❌ That `net_realisation` is finished. It's missing the market fee and the price range.
- ❌ Any number not in the table above.

If you don't know, say **"I don't know, let me check"**. With a decision log and a task backlog in
the repo, that answer looks organised. A confident wrong answer that a teammate then contradicts
does not.

---

## Before the day

- [ ] Everyone has read this document.
- [ ] Agree who says what, and who fields questions about which module.
- [ ] Agree our line on how we used AI tooling, so all three answers match. Whatever we say, we say
      the same thing — and we should each be able to explain any code we're credited with.
- [ ] One full rehearsal against a clock.
