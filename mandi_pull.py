#!/usr/bin/env python3
"""
MandiWise — data.gov.in puller and first-pass analysis.

Two jobs:
  1. Snapshot today's mandi prices to a dated JSON file (run this daily,
     starting today — this endpoint has no history, so anything you don't
     capture is gone).
  2. Compute price dispersion across mandis and reporting coverage from
     whatever snapshots you have.

Usage:
    export DATAGOV_API_KEY=your_key_here
    python mandi_pull.py pull            # snapshot today
    python mandi_pull.py analyse         # analyse all snapshots on disk
    python mandi_pull.py pull --state Haryana

VERIFIED 2026-09-03: endpoint live, schema as below, state filter and
offset pagination both work.
"""

import json
import os
import sys
import time
import argparse
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE = "https://api.data.gov.in/resource/" + RESOURCE_ID
DATA_DIR = "data"
PAGE_SIZE = 1000          # sample key forces 10; a real key allows more
REQUEST_PAUSE = 0.3

# Verified 2026-09-04 on a Punjab pull: modal_price sometimes reports
# placeholder/bad values (seen: Rs 0.10-0.18, all from one mandi, one day).
# Real prices in that pull started around Rs 200. Rs 50 sits in the gap
# between the two clusters -- reject anything below it rather than let it
# blow up dispersion ratios. This is a rejection, not a guess: see
# docs/DECISIONS.md.
PRICE_FLOOR = 50

# claude.md's liquidity measure is defined over a trailing 30-day window.
LIQUIDITY_WINDOW_DAYS = 30


def load_dotenv(path=".env"):
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def get_key():
    load_dotenv()
    key = os.environ.get("DATAGOV_API_KEY")
    if not key:
        sys.exit(
            "DATAGOV_API_KEY is not set.\n"
            "Get a key: data.gov.in -> My Account -> Generate Your New API KEY\n"
            "Then put it in .env as DATAGOV_API_KEY=your_key_here, "
            "or: export DATAGOV_API_KEY=your_key_here"
        )
    return key


def fetch_page(key, state, offset, retries=4, request_timeout=20):
    params = {
        "api-key": key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": offset,
        "filters[state]": state,
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    # The API gateway silently drops requests whose User-Agent contains
    # "python" (verified 2026-09-04) -- no error, just a hang to timeout.
    # Any non-Python-looking UA works.
    req = urllib.request.Request(url, headers={"User-Agent": "MandiWise-DataPuller/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                return json.load(resp)
        except Exception as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print("  fetch failed (%s), retrying in %ds... (%d/%d)"
                  % (exc, wait, attempt + 1, retries), file=sys.stderr)
            time.sleep(wait)


def pull(state):
    """Snapshot all of today's records for a state."""
    key = get_key()
    os.makedirs(DATA_DIR, exist_ok=True)

    first = fetch_page(key, state, 0)
    total = int(first.get("total", 0))
    returned = len(first.get("records", []))
    print("%s: %d records available, %d per page" % (state, total, returned))

    if returned < PAGE_SIZE and returned < total:
        print("  NOTE: page size capped at %d. If you are using the public "
              "sample key, switch to your own." % returned)

    rows = list(first.get("records", []))
    page = returned or PAGE_SIZE
    offset = page
    while offset < total:
        rows += fetch_page(key, state, offset).get("records", [])
        offset += page
        print("  %d / %d" % (min(offset, total), total), end="\r")
        time.sleep(REQUEST_PAUSE)

    path = os.path.join(
        DATA_DIR, "%s_%s.json" % (state.lower().replace(" ", "_"),
                                  date.today().isoformat())
    )
    with open(path, "w") as fh:
        json.dump(rows, fh)

    dates = sorted({r.get("arrival_date") for r in rows})
    print("\nSaved %d rows -> %s" % (len(rows), path))
    print("arrival_date values present: %s" % dates)
    if len(dates) == 1:
        print("Confirms: this endpoint carries a single day. Run this daily.")
    return rows


def _parse_date(text):
    """Rows carry DD/MM/YYYY (both sources are normalised to it)."""
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def load_snapshots():
    if not os.path.isdir(DATA_DIR):
        sys.exit("No %s/ directory. Run 'pull' first." % DATA_DIR)
    rows, files = [], sorted(os.listdir(DATA_DIR))
    for name in files:
        if name.endswith(".json"):
            with open(os.path.join(DATA_DIR, name)) as fh:
                rows += json.load(fh)

    # data.gov.in snapshots and CEDA backfills can cover the same reading.
    # Dedupe so an overlapping day is not counted twice.
    seen, unique = set(), []
    for r in rows:
        key = (r.get("arrival_date"), r.get("market"), r.get("commodity"),
               r.get("variety"), r.get("grade"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    dropped = len(rows) - len(unique)
    print("Loaded %d rows from %d snapshot file(s)%s"
          % (len(unique), len(files),
             " (%d duplicate row(s) dropped)" % dropped if dropped else ""))
    return unique


def analyse(rows):
    """
    Price dispersion is CROSS-SECTIONAL: it compares markets against each
    other on the SAME DAY. One snapshot is therefore enough for a first
    result. More days make the result more robust, not merely possible.

    Only like is compared with like -- same commodity, variety and grade.
    Comparing across grades measures quality difference, not opportunity.
    """
    groups = defaultdict(list)
    rejected = []
    for r in rows:
        try:
            modal = float(r["modal_price"])
        except (KeyError, TypeError, ValueError):
            continue
        if modal < PRICE_FLOOR:
            rejected.append(r)
            continue
        key = (r.get("arrival_date"), r.get("commodity"),
               r.get("variety"), r.get("grade"))
        groups[key].append((r.get("market"), modal))

    if rejected:
        print("\nRejected %d row(s) below the Rs %d price floor "
              "(placeholder/bad data, not real prices):" % (len(rejected), PRICE_FLOOR))
        for r in rejected:
            print("  %-24s %-24s Rs %s" % (
                (r.get("market") or "")[:24], (r.get("commodity") or "")[:24],
                r.get("modal_price")))

    # ---- dispersion ----
    results = []
    for (day, commodity, variety, grade), obs in groups.items():
        markets = {m: p for m, p in obs}
        if len(markets) < 3:          # need a real cross-section
            continue
        lo, hi = min(markets.values()), max(markets.values())
        results.append({
            "date": day, "commodity": commodity, "variety": variety,
            "grade": grade, "n_markets": len(markets),
            "min": lo, "max": hi, "dispersion": (hi - lo) / lo,
            "cheapest": min(markets, key=markets.get),
            "dearest": max(markets, key=markets.get),
        })

    print("\n" + "=" * 62)
    print("PRICE DISPERSION")
    print("=" * 62)
    if not results:
        print("No commodity had 3+ markets reporting. Pull more days or a "
              "larger state.")
    else:
        vals = sorted(r["dispersion"] for r in results)
        n = len(vals)
        print("Comparable groups: %d" % n)
        print("Median dispersion: %.1f%%" % (median(vals) * 100))
        print("25th percentile  : %.1f%%" % (vals[n // 4] * 100))
        print("75th percentile  : %.1f%%" % (vals[3 * n // 4] * 100))

        med = median(vals) * 100
        if med > 10:
            verdict = "STRONG - market selection is materially consequential"
        elif med >= 4:
            verdict = "CONDITIONAL - reframe as 'when is the trip worth it'"
        else:
            verdict = "WEAK - pivot to pooling and liquidity (see plan)"
        print("Verdict: %s" % verdict)

        print("\nTop 10 by dispersion (candidates for the report's Table II):")
        for r in sorted(results, key=lambda x: -x["dispersion"])[:10]:
            print("  %-28s %-12s %5.1f%%  %s (%.0f) -> %s (%.0f)" % (
                (r["commodity"] or "")[:28], (r["grade"] or "")[:12],
                r["dispersion"] * 100, (r["cheapest"] or "")[:18], r["min"],
                (r["dearest"] or "")[:18], r["max"]))

    # ---- liquidity: trailing 30-day window, per source ----
    #
    # claude.md specifies: "For each (mandi, commodity), count reporting days
    # in a trailing 30-day window." An earlier version divided each pair's
    # reporting days by every date in the corpus, which broke the moment the
    # corpus held two sources covering different years -- pairs from the
    # 2-day live feed scored ~0% against a 743-day denominator. The window is
    # therefore anchored per source, and the denominator is the number of days
    # the corpus actually observed inside that window, not a flat 30.
    by_source = defaultdict(list)
    for r in rows:
        by_source[r.get("source") or "data.gov.in"].append(r)

    print("\n" + "=" * 62)
    print("LIQUIDITY  (reporting days in a trailing %d-day window)"
          % LIQUIDITY_WINDOW_DAYS)
    print("=" * 62)

    for src in sorted(by_source):
        srows = by_source[src]
        dates = {d for d in (_parse_date(r.get("arrival_date")) for r in srows)
                 if d}
        if not dates:
            continue
        anchor = max(dates)
        start = anchor - timedelta(days=LIQUIDITY_WINDOW_DAYS - 1)
        observed = sorted(d for d in dates if start <= d <= anchor)

        pairs = defaultdict(set)
        for r in srows:
            d = _parse_date(r.get("arrival_date"))
            if d and start <= d <= anchor:
                pairs[(r.get("market"), r.get("commodity"))].add(d)

        print("\nsource: %s   window %s .. %s"
              % (src, start.isoformat(), anchor.isoformat()))
        print("  days the corpus observed in this window: %d of %d"
              % (len(observed), LIQUIDITY_WINDOW_DAYS))
        if len(observed) < LIQUIDITY_WINDOW_DAYS:
            print("  (a pair can report at most %d days here, so those are the"
                  " denominator -- not %d)"
                  % (len(observed), LIQUIDITY_WINDOW_DAYS))
        if not pairs or len(observed) < 2:
            print("  too few days to judge liquidity from this source yet.")
            continue

        counts = sorted(len(d) for d in pairs.values())
        share = [c / len(observed) for c in counts]
        print("  market-commodity pairs : %d" % len(counts))
        print("  reporting days  median : %d   (25th %d, 75th %d)"
              % (median(counts), counts[len(counts) // 4],
                 counts[3 * len(counts) // 4]))
        # Buckets are a provisional reading aid, not a sourced threshold.
        active = sum(1 for x in share if x >= 0.6)
        inter = sum(1 for x in share if 0.2 <= x < 0.6)
        sparse = sum(1 for x in share if x < 0.2)
        print("  active (>=60%% of observed days)   : %d" % active)
        print("  intermittent (20-60%%)            : %d" % inter)
        print("  sparse (<20%%, no reliable buyer) : %d" % sparse)
        print("  NOTE: those 60/20 cut-offs are provisional, not sourced.")

    # ---- naming inconsistency, evidence for the normalisation layer ----
    odd = sorted({r.get("commodity") for r in rows
                  if r.get("commodity") and
                  any(ch in r["commodity"] for ch in "()/")})
    if odd:
        print("\nCommodity names needing normalisation (%d):" % len(odd))
        for name in odd[:10]:
            print("  %s" % name)

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["pull", "analyse"])
    ap.add_argument("--state", default="Punjab")
    args = ap.parse_args()

    if args.command == "pull":
        analyse(pull(args.state))
    else:
        analyse(load_snapshots())


if __name__ == "__main__":
    main()
