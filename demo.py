"""Run the illustrative 40-quintal potato comparison from the project brief."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mandiwise.models import MandiOffer, PriceObservation, VehicleType  # noqa: E402
from mandiwise.recommendation import rank_mandis  # noqa: E402


ROOT = Path(__file__).parent


def main() -> None:
    vehicle_data = json.loads((ROOT / "data" / "vehicle_rates.json").read_text())
    vehicles = [VehicleType(**row) for row in vehicle_data["vehicles"]]
    offers = []
    with (ROOT / "data" / "example_market_prices.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            offers.append(
                MandiOffer(
                    price=PriceObservation(
                        mandi_name=row["mandi_name"],
                        commodity=row["commodity"],
                        modal_price_per_quintal=Decimal(row["modal_price_per_quintal"]),
                        reported_on=date.fromisoformat(row["reported_on"]),
                    ),
                    distance_km=Decimal(row["distance_km"]),
                    commission_rate=Decimal(row["commission_rate"]),
                    handling_cost_per_quintal=Decimal(row["handling_cost_per_quintal"]),
                )
            )
    # The illustrative individual-farmer scenario assumes a tempo is the
    # available vehicle. Pooling can later use the truck in the same rate card.
    individual_vehicles = [vehicle for vehicle in vehicles if vehicle.name == "Tempo"]
    ranked = rank_mandis(offers, 40, individual_vehicles, today=date(2026, 9, 17))
    print("MandiWise illustrative recommendation - 40 quintals of potato\n")
    for position, item in enumerate(ranked, 1):
        vehicles_used = ", ".join(f"{count} x {name}" for name, count in item.transport_plan.vehicles)
        print(f"{position}. {item.mandi_name}: INR {item.net_realisation_inr} net")
        print(
            f"   Gross {item.gross_revenue_inr} - commission {item.commission_inr} "
            f"- handling {item.handling_inr} - transport {item.transport_inr} ({vehicles_used})"
        )


if __name__ == "__main__":
    main()
