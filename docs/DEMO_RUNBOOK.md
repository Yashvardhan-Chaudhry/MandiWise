# Demo runbook — 10-minute progress demo

Presenter's script. Everything here runs from committed data. **Nothing in this runbook needs the
API key, the `.env` file, or an internet connection** — verified 2026-09-17.

> The two commands that DO touch the network and the key are `python mandi_pull.py pull` and
> `python ceda_pull.py`. **Never run either on screen.** They are how the data was collected, not
> part of the demo.

---

## Pre-flight — do this 30 minutes before, not on the day

1. **Start the server the safe way.** From `C:\Users\chaud\MandiWise\backend`:

   ```
   .venv\Scripts\python.exe -m mandiwise_transport.presentation
   ```

   **Do not use `START_DEMO.cmd` or `START_MANDIWISE.cmd` for the real demo.** They run
   `pip install -e .` on *every* launch, which must reach PyPI — on venue Wi-Fi that is a coin
   flip, and a demo that worked yesterday can fail today. The command above skips the install
   entirely and is already verified to work. Add `--port 8002` if 8001 is taken.

2. **Pre-stage the pooling portal.** It ships with no seed data — the trip list is empty until
   someone posts a trip. Before the demo:
   - Register account 1 at `http://127.0.0.1:8001/pooling`. **Password must be at least 15
     characters.**
   - Post a trip (origin, mandi, state, district, a travel date in the **future in Indian time**,
     distance, crop, your lot, vehicle rates).
   - Open a **second browser profile / incognito window**, register account 2, request to join.
   - Approve the join request from window 1.
   - Leave both windows open and logged in.

3. **Do not restart the server after staging.** The session secret is regenerated on every launch,
   so a restart silently logs both windows out — and the login throttle is 10 attempts per minute,
   which punishes retyping a 15-character password under pressure.

4. **Check the room.** `git status` clean · `.env` not open in any editor or tab · terminal font
   large enough to read from the back · close anything else using port 8001.

5. **Check `data/` holds only the committed snapshots.** If extra, untracked
   `punjab_2026-09-17.json` / `punjab_2026-09-23.json` pulls are sitting in `data/`, `analyse`
   loads them too and prints different figures (median 74.0% over 3,018 groups, not 73.1% over
   2,821). Run the demo from a clean checkout so the screen matches this runbook.

6. **Rehearse once against a clock.** Ten minutes is less than it sounds.

---

## Run of show

### 0:00–1:00 — The problem

No screen needed. The point to land: a farmer can see the government's published prices and still
not know where to sell, because **the highest price is not the best price** — commission scales
with price, transport does not scale with quantity.

Say plainly: *"We did not assume this was true. We tested it first."*

### 1:00–3:30 — Real data

```
python mandi_pull.py analyse
```

Runs in about 1.5 seconds against 17,742 committed rows. Two things scroll past that look like
errors and are actually the strongest evidence in the demo — **call them out before anyone asks**:

- `skipping vehicle_rates.json (not a price snapshot)` — the loader validates file shape instead of
  assuming every JSON in the folder is price data.
- **A 23-row rejection block** listing Patti APMC prices of ₹0.10–₹32.90 on 2026-09-04 (11 rows)
  and ₹0.08–₹25.30 on 2026-09-07 (12 rows). One mandi published placeholder prices on both live
  days we captured. We detect, reject and **log** them rather than averaging them in. *Without this
  guard a single green-chilli comparison on 2026-09-04 (₹0.10 against ₹3,808) computed as
  3,807,900% dispersion. The headline does not move — the median stays 73.1% (over 2,822 groups
  instead of 2,821) — so the guard protects individual comparisons, not the median.*

Then the result:

| | |
|---|---|
| Comparable groups | **2,821** same-day cross-sections |
| **Median dispersion** | **73.1%** |
| 25th percentile | 46.7% |
| Verdict | **STRONG** (our own threshold was >10%) |

The sentence that matters: *"Same crop, same grade, same day — the gap between the cheapest and
dearest mandi is 73% at the median. The premise holds."*

Immediately follow with the honesty line (see 8:30 below) if she looks like she's about to ask.

### 3:30–6:30 — Working software

**First, the engine:**

```
python demo.py
```

Instant. It opens with `PLACEHOLDER RATE CARD - NOT SOURCED … Do not quote these to a farmer.`
**Do not skip past that line — read it out.** It is the product refusing to let an unsourced number
pass as real, and it is exactly the discipline an examiner is looking for.

Then the ranking: the distant mandi nets ₹48,592 against the local mandi's ₹42,480, with the full
breakdown — gross, commission, handling, transport, and the vehicle count behind the transport.

**Then the portal** — switch to the already-open browser windows:
- `/demo` — the transport calculator. Needs no account, is prefilled, and shows the step function:
  cost per quintal jumps at vehicle capacity boundaries. **This is the whole reason pooling works**,
  and it is the most visual thing in the demo.
- `/pooling` — the staged trip, the join request, the approval, and the cost split by quantity.
  Point out that each farmer's lot stays separate: we pool the *vehicle*, not the produce.

### 6:30–8:30 — Engineering rigour

Keep this fast and concrete. Show, don't describe:

```
python -m unittest discover -s tests
cd backend && uv run --extra test pytest
```

**55 tests** (5 root, 50 backend, 1 skipped). Then open two files on screen:

- `docs/DECISIONS.md` — append-only. Every design choice with its reasoning, including the ones we
  reversed and *why the original reasoning stopped holding*. Nothing is ever edited out.
- `docs/TASKS.md` — the backlog, including defects we found by auditing our own merged work.

If there's time, one line on `research/engine_benchmark.md`: two of us independently wrote a
vehicle-packing solver, so we benchmarked them against each other over 3,000 randomised cases —
zero disagreements on cost — and chose one on scaling and test coverage rather than on opinion.

### 8:30–10:00 — What we do not claim

This is the part that earns trust. Deliver it deliberately, not apologetically:

> "We have validated the **premise** — prices genuinely do not cluster. We have **not** proven the
> product claim, because that is net realisation after real transport costs, and our transport
> rates are still placeholders. That is our blocking next step, and it is a phone call to a
> transporter, not a coding problem."

Then next steps: source real rates · finish `net_realisation` (it is missing the market fee and the
min/max price range) · the multilingual UI · deploy.

---

## If something breaks

| Problem | Do this |
|---|---|
| Server won't start | Use the pre-flight command, not the `.cmd` files. `--port 8002` if 8001 is busy. |
| Logged out of the portal | Do not restart the server — log back in slowly; 10 attempts/minute limit. |
| Portal misbehaves entirely | Drop it. `python demo.py` and `python mandi_pull.py analyse` are offline, instant, and carry the strongest content anyway. |
| Asked for something not built | "Not built yet — it's in `docs/TASKS.md` with acceptance criteria." Never improvise a yes. |
| Running long | Cut the benchmark and the backend test suite. Never cut the 8:30 honesty slot. |
