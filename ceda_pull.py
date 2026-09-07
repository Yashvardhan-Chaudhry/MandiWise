#!/usr/bin/env python3
"""
MandiWise -- CEDA Agri Market Data backfill.

The data.gov.in feed (see mandi_pull.py) carries only the current day, so
building history there means waiting. CEDA (Centre for Economic Data &
Analysis, Ashoka University) republishes the same DMI/AGMARKNET source with
history back to 2000, and exposes daily mandi-level PRICES and ARRIVAL
QUANTITIES over a free JSON API.

Rows are normalised into the same shape mandi_pull.py writes, so
`python mandi_pull.py analyse` reads both sources out of data/.

Usage:
    python ceda_pull.py list-districts --state 3
    python ceda_pull.py list-commodities --search potato
    python ceda_pull.py backfill --districts 48,40,41 --commodities 1,24 --days 30

ATTRIBUTION (required by CEDA's terms -- free for NON-COMMERCIAL use only):
    "CEDA Agri Market Data (CEDA-AMD), 2000-2023. Centre for Economic Data &
    Analysis, Ashoka University"
Their logo must appear on any published visual. If MandiWise is ever
commercialised this source must be re-sourced. See docs/DECISIONS.md.

VERIFIED 2026-09-04: /states, /districts, /commodities, /prices and
/quantities all live and returning data; rate limit confirmed real.
"""

import json
import os
import sys
import time
import argparse
import urllib.error
import urllib.request
from datetime import date, timedelta

API = "https://agmarknet.ceda.ashoka.edu.in/api"
DATA_DIR = "data"
# CEDA's gateway drops Python's default User-Agent the same way data.gov.in
# does, so send a real one.
USER_AGENT = "MandiWise-Research/1.0"
DEFAULT_PACE = 600          # seconds between requests; this API limits hard
DEFAULT_MAX_WAIT = 660      # 11 min -- their observed cooldown is ~10

# Verified 2026-09-07: a response of exactly this many rows is TRUNCATED, not
# complete. A 2-year onion request returned exactly 1000. Split and re-request.
PAGE_CAP = 1000

# Raw per-request results live here, inside DATA_DIR but in a subdirectory so
# mandi_pull.load_snapshots() (which reads *.json directly in data/) ignores them.
CACHE_SUBDIR = "_ceda_cache"

# Verified 2026-09-07: when throttled the API sometimes answers 200 with an
# empty data list instead of an error, so an empty result is not evidence of
# absent data. Every empty is re-probed once after a pause before being
# believed -- an earlier run without this recorded "no data" for ranges that
# demonstrably do have data.
EMPTY_RECHECK_PAUSE = 90


class RateLimited(Exception):
    def __init__(self, retry_after_s):
        self.retry_after_s = retry_after_s
        super().__init__("rate limited for %ds" % retry_after_s)


def load_dotenv(path=".env"):
    """Same minimal loader as mandi_pull.py -- no external dependency."""
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _request(path, payload=None, retries=3, timeout=45):
    """GET when payload is None, else POST JSON. Raises RateLimited."""
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data:
        headers["Content-Type"] = "application/json"

    # The anonymous portal endpoint needs no key; a registered CEDA key is
    # sent when present so switching to it is config, not a rewrite.
    load_dotenv()
    key = os.environ.get("CEDA_API_KEY")
    if key:
        headers["Authorization"] = "Bearer %s" % key

    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as exc:
            # Rate limiting arrives two ways: a real 429, or a 200 whose body
            # carries an "error" field (handled below). Both mean wait.
            if exc.code == 429:
                hdr = exc.headers.get("Retry-After")
                if hdr and hdr.isdigit():
                    # Spec says seconds, but CEDA sends milliseconds. Anything
                    # over a day is certainly ms, so normalise it.
                    val = int(hdr)
                    raise RateLimited((val // 1000 if val > 86400 else val) + 5)
                raise RateLimited(DEFAULT_MAX_WAIT)
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print("  request failed (%s), retrying in %ds... (%d/%d)"
                  % (exc, wait, attempt + 1, retries), file=sys.stderr)
            time.sleep(wait)
            continue
        except Exception as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print("  request failed (%s), retrying in %ds... (%d/%d)"
                  % (exc, wait, attempt + 1, retries), file=sys.stderr)
            time.sleep(wait)
            continue

        # The API reports rate limiting in a 200 body, not an HTTP status.
        err = body.get("error") if isinstance(body, dict) else None
        if err:
            if "too many" in err.lower():
                ms = body.get("retryAfter") or 0
                raise RateLimited(int(ms / 1000) + 5)
            raise RuntimeError("API error: %s" % err)
        return body


def list_states():
    for s in _request("/states")["data"]:
        print("%4d  %s" % (s["census_state_id"], s["census_state_name"]))


def list_districts(state_id):
    for d in _request("/districts?state_id=%d" % state_id)["data"]:
        print("%4d  %s" % (d["census_district_id"], d["census_district_name"]))


def list_commodities(search):
    rows = _request("/commodities")["data"]
    if search:
        needle = search.lower()
        rows = [c for c in rows if needle in c["commodity_disp_name"].lower()]
    for c in rows:
        print("%4d  %s" % (c["commodity_id"], c["commodity_disp_name"]))
    if search and not rows:
        print("No commodity matched %r." % search)


def _iso_to_ddmmyyyy(iso):
    """CEDA reports 2025-04-30; data.gov.in reports 30/04/2025. Normalise to
    the latter so both sources group together in analyse()."""
    y, m, d = iso.split("-")
    return "%s/%s/%s" % (d, m, y)


def _normalise(price_rows, qty_rows):
    """CEDA schema -> the data.gov.in row shape mandi_pull.analyse() expects.

    CEDA has no grade field; it is left empty rather than guessed. Arrival
    quantity is attached where a matching (date, market, commodity) exists --
    this is the field the live data.gov.in feed does not carry at all.
    """
    qty_by_key = {}
    for q in qty_rows:
        key = (q.get("t"), q.get("market_id"), q.get("cmdty"))
        qty_by_key[key] = q.get("qty")

    out = []
    for p in price_rows:
        key = (p.get("t"), p.get("market_id"), p.get("cmdty"))
        out.append({
            "state": p.get("state_name"),
            "district": p.get("district_name"),
            "market": p.get("market_name"),
            "commodity": p.get("cmdty"),
            "variety": p.get("variety"),
            "grade": "",
            "arrival_date": _iso_to_ddmmyyyy(p["t"]) if p.get("t") else None,
            "min_price": p.get("p_min"),
            "max_price": p.get("p_max"),
            "modal_price": p.get("p_modal"),
            "arrivals_qty": qty_by_key.get(key),
            "source": "ceda",
        })
    return out


def _payload(state_id, district_id, commodity_id, start, end):
    return {
        "state_id": state_id,
        "district_id": district_id,
        "commodity_id": commodity_id,
        "start_date": start,
        "end_date": end,
        "calculation_type": "d",
        "chart_type": "datadownload",
    }


def _cache_path(endpoint, state_id, district_id, commodity_id, start, end):
    """One file per actual API request. Chunking means a single combination
    can take a dozen requests; caching at the combination level (as an earlier
    version did) threw all of them away whenever the rate limit hit mid-way,
    so a dense commodity could never finish. Cache the leaf, not the combo.

    Lives in a subdirectory so mandi_pull.load_snapshots(), which globs *.json
    directly inside data/, does not read these raw partials as snapshots.
    """
    cache_dir = os.path.join(DATA_DIR, CACHE_SUBDIR)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "%s_%d_%d_%d_%s_%s.json" % (
        endpoint.strip("/"), state_id, district_id, commodity_id, start, end))


def _fetch_verified(endpoint, payload, pace):
    """One request, with an empty result re-probed once before it is believed.

    A throttled CEDA response can be a 200 carrying an empty data list, which
    is indistinguishable from "this range genuinely has no data" unless you
    ask again. Returns (rows, empty_confirmed).
    """
    rows = _request(endpoint, payload)["data"]
    if rows:
        return rows, False

    print("    empty result -- re-probing in %ds to rule out silent throttling"
          % EMPTY_RECHECK_PAUSE)
    time.sleep(EMPTY_RECHECK_PAUSE)
    rows = _request(endpoint, payload)["data"]
    if rows:
        print("    second probe returned %d rows -- the first empty WAS a "
              "throttle artifact" % len(rows))
        return rows, False
    return [], True


def _fetch_range(endpoint, state_id, district_id, commodity_id,
                 start, end, pace, max_wait, depth=0):
    """Fetch one date range, splitting it when the response hits the row cap.

    A response of exactly PAGE_CAP rows is truncated, so the range is halved
    and each half fetched separately until every piece comes back under the
    cap. Every leaf result is cached to disk the moment it arrives, so a rate
    limit costs only the in-flight request rather than the whole combination.
    """
    path = _cache_path(endpoint, state_id, district_id, commodity_id, start, end)
    capped_marker = path + ".capped"

    if os.path.isfile(path):
        with open(path) as fh:
            return json.load(fh)

    # A range already known to be truncated goes straight to splitting, rather
    # than spending a request to rediscover that it caps.
    if os.path.isfile(capped_marker):
        rows = [None] * PAGE_CAP        # only its length is used, to force the split
    else:
        payload = _payload(state_id, district_id, commodity_id, start, end)

        # Wait out rate limits on THIS leaf rather than abandoning the
        # combination -- everything already fetched is on disk, so waiting is
        # cheap and nothing is re-requested afterwards.
        while True:
            try:
                rows, _ = _fetch_verified(endpoint, payload, pace)
                break
            except RateLimited as rl:
                if rl.retry_after_s > max_wait:
                    raise
                print("    rate limited, waiting %ds (%s..%s)"
                      % (rl.retry_after_s, start, end))
                time.sleep(rl.retry_after_s)

        if len(rows) >= PAGE_CAP:
            with open(capped_marker, "w") as fh:
                fh.write("truncated at %d rows; split this range\n" % PAGE_CAP)

    if len(rows) < PAGE_CAP:
        with open(path, "w") as fh:
            json.dump(rows, fh)
        return rows

    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    if d0 >= d1:
        print("    WARNING: a single day (%s) still hits the %d-row cap; "
              "data may be incomplete." % (start, PAGE_CAP), file=sys.stderr)
        return rows

    mid = d0 + (d1 - d0) // 2
    print("    hit the %d-row cap, splitting %s..%s" % (PAGE_CAP, start, end))
    time.sleep(pace)
    left = _fetch_range(endpoint, state_id, district_id, commodity_id,
                        start, mid.isoformat(), pace, max_wait, depth + 1)
    time.sleep(pace)
    right = _fetch_range(endpoint, state_id, district_id, commodity_id,
                         (mid + timedelta(days=1)).isoformat(), end,
                         pace, max_wait, depth + 1)
    return left + right


def _fetch_combo(state_id, district_id, commodity_id, start, end, want_qty,
                 pace, max_wait):
    prices = _fetch_range("/prices", state_id, district_id, commodity_id,
                          start, end, pace, max_wait)
    qty = []
    if want_qty and prices:
        time.sleep(pace)
        qty = _fetch_range("/quantities", state_id, district_id, commodity_id,
                           start, end, pace, max_wait)
    return _normalise(prices, qty)


def backfill(state_id, districts, commodities, start, end, want_qty, max_wait,
             pace):
    """Resumable: one file per (district, commodity); existing files are
    skipped, so a run stopped by the rate limit can simply be re-run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    combos = [(d, c) for d in districts for c in commodities]
    print("%d combination(s), %s to %s, pacing %ds between requests"
          % (len(combos), start, end, pace))

    done = skipped = rows_total = 0
    for i, (district_id, commodity_id) in enumerate(combos, 1):
        path = os.path.join(DATA_DIR, "ceda_%d_%d_%d_%s_%s.json"
                            % (state_id, district_id, commodity_id, start, end))
        if os.path.isfile(path):
            skipped += 1
            continue

        label = "district %d / commodity %d" % (district_id, commodity_id)
        print("  [%d/%d] fetching %s..." % (i, len(combos), label))
        try:
            rows = _fetch_combo(state_id, district_id, commodity_id,
                                start, end, want_qty, pace, max_wait)
        except RateLimited as rl:
            # Leaf results are already cached, so stopping here loses at most
            # the one in-flight request; re-running picks up where this left off.
            print("\nRate limited for %ds, beyond --max-wait %ds."
                  % (rl.retry_after_s, max_wait))
            print("Every completed request is cached. Re-run the same command "
                  "later to resume -- it will not re-fetch what it already has.")
            break

        with open(path, "w") as fh:
            json.dump(rows, fh)
        done += 1
        rows_total += len(rows)
        n_qty = sum(1 for r in rows if r.get("arrivals_qty") is not None)
        days = len({r.get("arrival_date") for r in rows})
        print("       %d rows, %d days, %d with arrivals -> %s"
              % (len(rows), days, n_qty, os.path.basename(path)))
        time.sleep(pace)

    print("\nFetched %d combination(s), skipped %d already on disk, %d rows total."
          % (done, skipped, rows_total))
    if done or skipped:
        print("Now run: python mandi_pull.py analyse")


def _parse_ids(text):
    return [int(x) for x in text.split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list-states")

    p_d = sub.add_parser("list-districts")
    p_d.add_argument("--state", type=int, default=3, help="census state id (Punjab=3)")

    p_c = sub.add_parser("list-commodities")
    p_c.add_argument("--search", default=None, help="filter by name substring")

    p_b = sub.add_parser("backfill")
    p_b.add_argument("--state", type=int, default=3)
    p_b.add_argument("--districts", required=True,
                     help="comma-separated census district ids")
    p_b.add_argument("--commodities", required=True,
                     help="comma-separated commodity ids")
    p_b.add_argument("--days", type=int, default=30,
                     help="days back from --end (default 30)")
    p_b.add_argument("--end", default=None,
                     help="end date YYYY-MM-DD (default: today)")
    p_b.add_argument("--no-quantities", action="store_true",
                     help="skip arrival volumes (halves the request count)")
    p_b.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT,
                     help="give up if the rate-limit cooldown exceeds this")
    p_b.add_argument("--pace", type=int, default=DEFAULT_PACE,
                     help="seconds between requests (default %d; this API "
                          "rate-limits hard, do not lower it casually)"
                          % DEFAULT_PACE)
    p_b.add_argument("--start", default=None,
                     help="start date YYYY-MM-DD (overrides --days)")

    args = ap.parse_args()

    if args.command == "list-states":
        list_states()
    elif args.command == "list-districts":
        list_districts(args.state)
    elif args.command == "list-commodities":
        list_commodities(args.search)
    elif args.command == "backfill":
        end = date.fromisoformat(args.end) if args.end else date.today()
        start = (date.fromisoformat(args.start) if args.start
                 else end - timedelta(days=args.days))
        backfill(args.state, _parse_ids(args.districts),
                 _parse_ids(args.commodities), start.isoformat(), end.isoformat(),
                 not args.no_quantities, args.max_wait, args.pace)


if __name__ == "__main__":
    main()
