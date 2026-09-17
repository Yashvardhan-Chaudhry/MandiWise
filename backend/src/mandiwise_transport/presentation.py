"""A classroom calculator and a separate saved farmer pooling portal.

The calculator stays stateless; the local launcher also enables persisted farmer pools.
Run `python -m mandiwise_transport.presentation` for a local, browser-opening demo.
"""

from decimal import Decimal
from importlib.resources import files
from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import Field, model_validator

from .engine import Vehicle, kg, optimise, paise, pool_quote, rupees
from .schemas import Input, Quantity, Text, VehicleInput

router = APIRouter(tags=["presentation"])


class Farmer(Input):
    name: Text
    quantity_quintals: Quantity


class Calculation(Input):
    distance_km: Annotated[Decimal, Field(gt=0, le=2000, decimal_places=3)]
    farmers: Annotated[list[Farmer], Field(min_length=1, max_length=8)]
    vehicles: Annotated[list[VehicleInput], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def limits(self):
        if sum(f.quantity_quintals for f in self.farmers) > 1000:
            raise ValueError("Keep the combined load at or below 1000 quintals")
        if len({v.code for v in self.vehicles}) != len(self.vehicles):
            raise ValueError("Vehicle codes must be unique")
        return self


@router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_page():
    return (
        files("mandiwise_transport")
        .joinpath("web/templates/transport_demo.html")
        .read_text(encoding="utf-8")
    )


@router.get("/demo/vehicles.js", include_in_schema=False)
def vehicle_script():
    from fastapi.responses import Response

    return Response(
        files("mandiwise_transport").joinpath("web/static/vehicles.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@router.post("/demo/calculate")
def calculate(body: Calculation):
    """Use caller-entered classroom inputs, not saved production configuration."""
    vehicles = [
        Vehicle(
            v.code,
            kg(v.capacity_quintals),
            paise(v.base_cost_inr + v.per_km_inr * body.distance_km),
        )
        for v in body.vehicles
    ]
    quantities = {f"farmer-{i + 1}": kg(f.quantity_quintals) for i, f in enumerate(body.farmers)}
    result = pool_quote(quantities, vehicles)
    solo = {key: optimise(quantity, vehicles) for key, quantity in quantities.items()}
    for participant in result["participants"]:
        index = int(participant["participant_id"].split("-")[1]) - 1
        participant["name"] = body.farmers[index].name
        participant["solo_vehicles"] = solo[participant["participant_id"]]["vehicles"]
    result["individual_total_inr"] = rupees(sum(p["cost_paise"] for p in solo.values()))
    result["rate_breakdown"] = [
        {
            "code": v.code,
            "capacity_quintals": str(v.capacity_quintals),
            "base_cost_inr": str(v.base_cost_inr),
            "per_km_inr": str(v.per_km_inr),
            "trip_cost_inr": rupees(vehicle.cost_paise),
        }
        for v, vehicle in zip(body.vehicles, vehicles)
    ]
    result["distance_km"] = str(body.distance_km)
    result["input_kind"] = "user_entered_demonstration"
    return result


def create_demo_app(database_url=None, jwt_secret=None):
    import os
    import secrets

    from .api import create_app
    from .db import Base

    app = create_app(
        database_url or os.getenv("PORTAL_DATABASE_URL", "sqlite:///./portal.db"),
        jwt_secret or os.getenv("JWT_SECRET") or secrets.token_urlsafe(48),
    )
    # Local launcher only. Deployed installations must use Alembic migrations.
    Base.metadata.create_all(app.state.engine)
    return app


def main():
    import argparse
    import threading
    import time
    import urllib.request
    import webbrowser

    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1..65535")
    url = f"http://127.0.0.1:{args.port}/demo"

    def open_when_ready():
        for _ in range(50):
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(0.2)

    if not args.no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"MandiWise presentation page: {url}\nKeep this terminal open. Ctrl+C stops the demo.")
    uvicorn.run(create_demo_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
