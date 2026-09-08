from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=160)]
Quantity = Annotated[Decimal, Field(gt=0, le=1000, decimal_places=2, allow_inf_nan=False)]
Money = Annotated[Decimal, Field(ge=0, le=1000000, decimal_places=2, allow_inf_nan=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocationInput(Input):
    name: Text
    kind: Literal["origin", "mandi"]
    state: Text
    district: Text
    source: Annotated[str, Field(min_length=1, max_length=500)]


class RouteInput(Input):
    origin_id: Text
    destination_id: Text
    distance_km: Annotated[Decimal, Field(gt=0, le=2000, decimal_places=3)]
    source: Annotated[str, Field(min_length=1, max_length=500)]
    effective_from: date
    effective_until: date

    @model_validator(mode="after")
    def valid_interval(self):
        if self.effective_until < self.effective_from:
            raise ValueError("effective_until must be on or after effective_from")
        if self.origin_id == self.destination_id:
            raise ValueError("Origin and destination must differ")
        return self


class VehicleInput(Input):
    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
    capacity_quintals: Quantity
    base_cost_inr: Money
    per_km_inr: Money

    @model_validator(mode="after")
    def positive_cost(self):
        if self.base_cost_inr == 0 and self.per_km_inr == 0:
            raise ValueError("Vehicle must have a positive rate")
        return self


class RateCardInput(Input):
    name: Text
    origin_id: Text
    destination_id: Text
    source: Annotated[str, Field(min_length=1, max_length=500)]
    effective_from: date
    effective_until: date
    is_demo: bool = False
    vehicles: Annotated[list[VehicleInput], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def validate_card(self):
        if self.effective_until < self.effective_from:
            raise ValueError("effective_until must be on or after effective_from")
        if len({v.code for v in self.vehicles}) != len(self.vehicles):
            raise ValueError("Vehicle codes must be unique within a card")
        if self.origin_id == self.destination_id:
            raise ValueError("Origin and destination must differ")
        return self


class QuoteInput(Input):
    route_id: Text
    rate_card_id: Text
    travel_date: date
    quantity_quintals: Quantity


class ParticipantInput(Input):
    participant_id: Text
    quantity_quintals: Quantity


class PoolQuoteInput(Input):
    route_id: Text
    rate_card_id: Text
    travel_date: date
    participants: Annotated[list[ParticipantInput], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def unique_members(self):
        if len({p.participant_id for p in self.participants}) != len(self.participants):
            raise ValueError("Participant IDs must be unique")
        if sum(p.quantity_quintals for p in self.participants) > 1000:
            raise ValueError("Pool cannot exceed 1000 quintals")
        return self


class PoolInput(Input):
    route_id: Text
    rate_card_id: Text
    travel_date: date
    commodity: Text
    pickup_description: Annotated[str, Field(min_length=1, max_length=500)]
    max_quantity_quintals: Quantity


class JoinInput(Input):
    quantity_quintals: Quantity
    variety: Text
    grade: Text
    condition: Annotated[str, Field(min_length=1, max_length=500)]


class VersionInput(Input):
    expected_version: Annotated[int, Field(ge=1)]


class ReviewInput(VersionInput):
    decision: Literal["APPROVED", "REJECTED"]


class TransitionInput(VersionInput):
    target: Literal["LOCKED", "DISPATCHED", "SETTLED", "CANCELLED"]
    transport_reference: Annotated[str | None, Field(min_length=1, max_length=300)] = None
    note: Annotated[str | None, Field(min_length=1, max_length=500)] = None
