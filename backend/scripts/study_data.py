"""Read-only, reproducible inventory of the repository's five frozen datasets."""

import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def study(directory):
    result = []
    identity = ("state", "district", "market", "commodity", "variety", "grade", "arrival_date")
    for path in sorted(Path(directory).glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        dates = [datetime.strptime(r["arrival_date"], "%d/%m/%Y").date() for r in rows]
        keys = Counter(tuple(r.get(k) for k in identity) for r in rows)
        prices = [
            tuple(Decimal(str(r[k])) for k in ("min_price", "modal_price", "max_price"))
            for r in rows
        ]
        result.append(
            {
                "file": path.name,
                "rows": len(rows),
                "first_date": str(min(dates)),
                "last_date": str(max(dates)),
                "reporting_days": len(set(dates)),
                "markets": len({(r["state"], r["district"], r["market"]) for r in rows}),
                "commodities": len({r["commodity"] for r in rows}),
                "duplicate_identity_rows": sum(n - 1 for n in keys.values()),
                "missing_grade": sum(not r.get("grade") for r in rows),
                "arrival_quantity_present": sum(r.get("arrivals_qty") is not None for r in rows),
                "modal_below_50": sum(modal < 50 for lo, modal, hi in prices),
                "invalid_price_order": sum(not lo <= modal <= hi for lo, modal, hi in prices),
                "fields": sorted(set().union(*(r.keys() for r in rows))),
            }
        )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="../data")
    print(json.dumps(study(parser.parse_args().data_dir), indent=2, ensure_ascii=False))
