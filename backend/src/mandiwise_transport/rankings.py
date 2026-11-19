"""Mandi ranking routes: validation and serialisation only.

Arithmetic lives in engine.py; inputs are read by pricing.py. These routes are
public and read-only, so they are input-capped and throttled per client.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import Field

from . import pricing
from . import services as svc
from .schemas import Input, Quantity

router = APIRouter(tags=["ranking"])

Name = Annotated[str, Field(min_length=1, max_length=160)]
Distance = Annotated[Decimal, Field(ge=0, le=2000, decimal_places=3, allow_inf_nan=False)]


class Candidate(Input):
    market: Name
    district: Name | None = None
    distance_km: Distance


class RankingRequest(Input):
    commodity: Name
    quantity_quintals: Quantity
    candidates: Annotated[list[Candidate], Field(min_length=1, max_length=10)]


def _inputs(request: Request) -> pricing.Inputs:
    try:
        return pricing.inputs_for(request.app)
    except pricing.PricingUnavailable as exc:
        raise svc.DomainError("prices_unavailable", str(exc), 503) from exc


def _today(request: Request):
    return getattr(request.app.state, "today", svc.today)()


@router.get("/v1/commodities")
def commodities(request: Request):
    """Commodity names present in the committed price snapshots."""
    return pricing.commodities(_inputs(request))


@router.get("/v1/markets")
def markets(request: Request, commodity: Annotated[str, Query(min_length=1, max_length=160)]):
    """Latest dated price per market for one commodity. Stale prices are flagged."""
    return pricing.markets(_inputs(request), commodity, _today(request))


@router.post("/v1/rankings")
def rankings(request: Request, body: RankingRequest):
    """Rank candidate mandis by net realisation, with the full breakdown and range."""
    from .portal import throttle

    throttle(request, "ranking", 30)
    return pricing.rank(
        _inputs(request), body.commodity, body.quantity_quintals, body.candidates, _today(request)
    )
