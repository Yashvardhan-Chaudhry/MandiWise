# Demo runbook — 10-minute presentation

This is the presenter's script. Everything here runs from committed data and needs **no API key,
no `.env` and no internet on the day**. The one exception is the first `npm ci`, which is part of
pre-flight. The story and the safe numbers are in `docs/DEMO_BRIEF.md`; read it first.

*Updated 2026-11-20. It now centres on the React client. The September run-of-show used the
server-rendered pages, which still exist at `/demo` and `/pooling` as a fallback.*

> `python mandi_pull.py pull` and `python ceda_pull.py` touch the network and the key. **Never run
> either on screen.** They are how the data was collected, not part of the demo.

---

## Pre-flight: do this the evening before, then again 30 minutes before

1. **Use a clean checkout of `main`.**
   - `git status` must show no untracked `data/punjab_2026-09-17.json` or
     `data/punjab_2026-09-23.json`.
   - If those files are present, `mandi_pull.py analyse` prints 74.0% over 3,018 groups instead of
     73.1% over 2,821, and the screen will not match the report.
2. **Start the backend the safe way.** From `backend\`:

   ```
   .venv\Scripts\python.exe -m mandiwise_transport.presentation --no-browser
   ```

   - Don't use the `.cmd` launchers on the day. They run `pip install` on every launch, which needs
     PyPI.
   - Add `--port 8002` if 8001 is taken; the frontend proxy expects 8001, though.
3. **Start the React client.** From `frontend\`:
   - Run `npm ci` once, the evening before; it needs internet.
   - Then run `npm run dev` and open **http://127.0.0.1:5173**. Use that exact host, not
     `localhost`, because the proxy's origin handling depends on it.
4. **Pre-stage pooling.** It ships with no data.
   - In the React client, register account 1 and post a trip for a **future** date in Indian time.
     Passwords need at least 15 characters.
   - In a second browser profile, register account 2 and request to join.
   - Approve the request from window 1, and leave both windows signed in.
5. **Do not restart the backend after staging.** The session secret changes on every launch, which
   signs everyone out, and sign-in is throttled to 10 attempts per minute.
6. **Room check:**
   - `.env` is not open anywhere;
   - the terminal font is readable from the back;
   - nothing else is listening on ports 8001 or 5173.
7. **Rehearse once against a clock.**

---

## Run of show

### 0:00–1:00: The problem (no screen)

A farmer can see the government's prices and still not know where to sell, because **the highest
price is not the best price.** Commission scales with the price, and transport is bought in whole
vehicles.

Say plainly: *"We did not assume this was true. We tested it first."*

### 1:00–3:00: The evidence (report figures, or `python mandi_pull.py analyse`)

- Show the report's potato figure: the cheapest vs the dearest Patiala mandi, week by week. The
  median weekly gap is 81.1% over 107 weeks.
- Then the headline: **73.1% median dispersion over 2,821 same-day comparisons.** Only 1.2% fall
  below our 10% bar, which we set before measuring.
- If you run `analyse` live, it takes about 1.5 s. Call out the 23-row rejection block before
  anyone asks: Patti APMC publishes placeholder prices of ₹0.08–₹32.90, and we reject and log them
  rather than average them in.

### 3:00–6:30: The product (React client)

1. **Choose a mandi** (`#rankings`). Enter:
   - Potato, 40 quintals;
   - tick **Patiala APMC** (15 km), **Khamano APMC** (35 km) and **Dera Bassi APMC** (60 km);
   - then **Compare net returns**.

   Expected results:

   | Rank | Mandi | Net |
   |---|---|---|
   | 1 | Dera Bassi | ₹53,200 |
   | 2 | Khamano | ₹34,500 |
   | 3 | Patiala | ₹21,460 |

   Point at three things:
   - **the warning banner:** read one line aloud, so the audience hears that the product refuses to
     pass a placeholder off as real;
   - **the STALE label with the price's age**;
   - **the breakdown summing exactly to the net.**

   Say: *"The screen does no arithmetic. Every number comes from the tested engine."*
2. **Transport calculator** (`#transport`). Two farmers with 40 q each, at 60 km. Each pays ₹3,200
   alone, or ₹1,850 when pooled into one truck. Cost per quintal is a step function, and **that is
   why pooling works.**
3. **Pooling** (`#pools`). Show the staged trip, the approval and the cost split by quantity. Each
   lot keeps its owner's identity; we pool the *vehicle*, not the produce.

### 6:30–8:30: Engineering rigour

```
python -m unittest discover -s tests
cd backend && uv run --extra test pytest -q
cd frontend && npm test
```

- The totals are **90 tests**: 5 root, 78 backend with 1 skipped, and 7 frontend. CI runs them on
  every pull request, plus a PostgreSQL job.
- Then show `docs/DECISIONS.md`, the append-only log that records reversals with reasons.
- If time allows, one line on the benchmark: two independent engines, 3,000 random cases, zero cost
  disagreements, and the DP chosen on speed (0.0259 s against 3.37 s at 8 vehicle types).

### 8:30–10:00: What we do not claim

Deliver this deliberately, not apologetically:

> "We have validated the **premise**: prices genuinely do not cluster. We have **not** proven the
> product claim, because that is net realisation after real costs, and our transport, commission
> and fee rates are still placeholders. The engine already has every term. Sourcing the rates is
> our next step, and it's a data change, not a code change."

Then the next steps: source real rates → re-run the validation on net values → daily ingestion →
verified translations → deployment.

---

## If something breaks

| Problem | Do this |
|---|---|
| Ranking screen shows a 404 or a "restart backend" message | The backend is an old process. Stop it and start it with the pre-flight command. |
| Vite says port 5173 is in use | A stale `node` process is holding it. Close it, then run `npm run dev` again. |
| Signed out of pooling | Don't restart the backend. Sign in slowly; the limit is 10 attempts per minute. |
| React client fails entirely | Fall back to `http://127.0.0.1:8001/demo` and `/pooling`, plus `python demo.py` (offline, instant). |
| Asked for something not built | "Not built yet; it's in `docs/TASKS.md` with acceptance criteria." Never improvise a yes. |
| Running long | Cut the test run and the benchmark. Never cut the 8:30 honesty slot. |
