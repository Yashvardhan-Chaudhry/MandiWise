"""Transparent net-realisation calculation and mandi ranking."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .models import MandiOffer, Recommendation, VehicleType, as_decimal
from .transport import cheapest_transport_plan


RUPEE = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP)


def calculate_recommendation(
    offer: MandiOffer,
    quantity_quintals: Decimal | int | float | str,
    vehicle_types: list[VehicleType] | tuple[VehicleType, ...],
    *,
    today: date | None = None,
    stale_after_days: int = 2,
) -> Recommendation:
    """Calculate the explained return for one mandi; this performs no I/O."""
    quantity = as_decimal(quantity_quintals, "quantity_quintals")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if stale_after_days < 0:
        raise ValueError("stale_after_days cannot be negative")
    transport_plan = cheapest_transport_plan(quantity, offer.distance_km, vehicle_types)
    gross = as_decimal(offer.price.modal_price_per_quintal, "modal_price") * quantity
    commission = gross * as_decimal(offer.commission_rate, "commission_rate")
    handling = as_decimal(offer.handling_cost_per_quintal, "handling") * quantity
    reference_day = today or date.today()
    return Recommendation(
        mandi_name=offer.price.mandi_name,
        commodity=offer.price.commodity,
        reported_on=offer.price.reported_on,
        is_stale=offer.price.reported_on < reference_day - timedelta(days=stale_after_days),
        modal_price_per_quintal=money(as_decimal(offer.price.modal_price_per_quintal, "modal_price")),
        quantity_quintals=quantity,
        gross_revenue_inr=money(gross),
        commission_inr=money(commission),
        handling_inr=money(handling),
        transport_inr=money(transport_plan.total_cost_inr),
        net_realisation_inr=money(gross - commission - handling - transport_plan.total_cost_inr),
        transport_plan=transport_plan,
    )


def rank_mandis(
    offers: list[MandiOffer] | tuple[MandiOffer, ...],
    quantity_quintals: Decimal | int | float | str,
    vehicle_types: list[VehicleType] | tuple[VehicleType, ...],
    **kwargs: object,
) -> list[Recommendation]:
    """Return recommendations highest net amount first; ties favour the nearer mandi."""
    # Each result is carried with the offer that produced it. Keying distance
    # by mandi name instead collapsed two offers for the same mandi into one
    # entry, so both rows sorted on whichever distance happened to win and the
    # "ties favour the nearer mandi" rule silently stopped applying.
    scored = [
        (offer, calculate_recommendation(offer, quantity_quintals, vehicle_types, **kwargs))
        for offer in offers
    ]
    scored.sort(
        key=lambda pair: (
            -pair[1].net_realisation_inr,
            pair[0].distance_km,
            pair[1].mandi_name,
        )
    )
    return [recommendation for _, recommendation in scored]
