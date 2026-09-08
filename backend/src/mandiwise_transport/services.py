"""Application rules: fetch persisted inputs, delegate all arithmetic to engine."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .db import Location, Member, PoolEvent, RateCard, Route
from .engine import Vehicle, kg, optimise, paise, pool_quote


def today():
    """Trip dates are Indian calendar dates, independent of server timezone."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status


def get(db, model, key):
    obj = db.get(model, key)
    if obj is None:
        raise DomainError("not_found", f"{model.__name__} not found", 404)
    return obj


def endpoints(db, origin, destination):
    first, last = get(db, Location, origin), get(db, Location, destination)
    if first.kind != "origin" or last.kind != "mandi":
        raise DomainError("invalid_route", "Route must connect a pickup origin to a mandi", 422)


def inputs(db, route_id, card_id, travel_date):
    route, card = get(db, Route, route_id), get(db, RateCard, card_id)
    if (route.origin_id, route.destination_id) != (card.origin_id, card.destination_id):
        raise DomainError("rate_route_mismatch", "Rate card is for a different pickup/mandi route")
    for obj in (route, card):
        if not obj.effective_from <= travel_date <= obj.effective_until:
            raise DomainError(
                "expired_inputs", "Travel date is outside route or rate-card validity"
            )
    vehicles = [
        Vehicle(
            v["code"],
            kg(Decimal(v["capacity_quintals"])),
            paise(
                Decimal(v["base_cost_inr"])
                + Decimal(v["per_km_inr"]) * Decimal(route.distance_m) / 1000
            ),
        )
        for v in card.vehicles
    ]
    provenance = {
        "route_id": route.id,
        "rate_card_id": card.id,
        "origin_id": route.origin_id,
        "destination_id": route.destination_id,
        "distance_km": str(Decimal(route.distance_m) / 1000),
        "distance_source": route.source,
        "rate_source": card.source,
        "rate_effective_from": str(card.effective_from),
        "rate_effective_until": str(card.effective_until),
        "distance_effective_from": str(route.effective_from),
        "distance_effective_until": str(route.effective_until),
        "travel_date": str(travel_date),
        "is_demo": card.is_demo,
        "warnings": [
            "Estimate only; fleet availability is not reserved.",
            "One shared pickup point; farm-to-pickup cost is excluded.",
            "Base + per-km rate must cover the agreed trip, including applicable extras.",
        ],
    }
    if card.is_demo:
        provenance["warnings"].append(
            "Synthetic demonstration rates; not a real transport quotation."
        )
    return vehicles, provenance


def quote(db, request):
    vehicles, provenance = inputs(db, request.route_id, request.rate_card_id, request.travel_date)
    if hasattr(request, "participants"):
        plan = pool_quote(
            {p.participant_id: kg(p.quantity_quintals) for p in request.participants}, vehicles
        )
    else:
        plan = optimise(kg(request.quantity_quintals), vehicles)
    return {**provenance, **plan}


def members(db, pool):
    return list(db.scalars(select(Member).where(Member.pool_id == pool.id).order_by(Member.id)))


def approved_quote(db, pool):
    vehicles, provenance = inputs(db, pool.route_id, pool.rate_card_id, pool.travel_date)
    quantities = {m.user_id: m.quantity_kg for m in members(db, pool) if m.status == "APPROVED"}
    if not quantities:
        raise DomainError("empty_pool", "Approve at least one member before quoting or locking")
    return {**provenance, **pool_quote(quantities, vehicles)}


def touch(db, pool, user, action, detail=None):
    # Every membership mutation also writes the parent version. Concurrent approvals,
    # joins and locks cannot both commit against the same capacity snapshot.
    pool.version += 1
    db.add(PoolEvent(pool_id=pool.id, actor_id=user.id, action=action, detail=detail or {}))


def manager(pool, user):
    if user.id != pool.coordinator_id:
        raise DomainError("forbidden", "Only this pool's coordinator may perform this action", 403)


def open_pool(pool):
    if pool.state != "OPEN":
        raise DomainError("pool_closed", "Membership can change only while the pool is OPEN")
    if pool.travel_date < today():
        raise DomainError("past_trip", "Cannot change membership for a past trip")


def version(pool, expected):
    if pool.version != expected:
        raise DomainError(
            "version_conflict", "Pool changed; reload and retry with its current version"
        )


def transition(db, pool, user, request):
    manager(pool, user)
    version(pool, request.expected_version)
    allowed = {
        "OPEN": {"LOCKED", "CANCELLED"},
        "LOCKED": {"DISPATCHED", "CANCELLED"},
        "DISPATCHED": {"SETTLED"},
        "SETTLED": set(),
        "CANCELLED": set(),
    }
    if request.target not in allowed[pool.state]:
        raise DomainError(
            "invalid_transition", f"Cannot move from {pool.state} to {request.target}"
        )
    if request.target == "LOCKED":
        open_pool(pool)
        if any(m.status == "PENDING" for m in members(db, pool)):
            raise DomainError("pending_members", "Review all pending join requests before locking")
        result = approved_quote(db, pool)
        if not result["all_participants_benefit"]:
            raise DomainError(
                "member_cost_increase", "A participant would pay more than travelling alone"
            )
        pool.locked_quote = result
    if request.target == "DISPATCHED":
        if not request.transport_reference:
            raise DomainError(
                "transport_required", "Record the coordinator's transport arrangement", 422
            )
        pool.transport_reference = request.transport_reference
    if request.target in {"SETTLED", "CANCELLED"} and not request.note:
        raise DomainError("note_required", "Record an outcome or cancellation note", 422)
    old = pool.state
    pool.state = request.target
    touch(db, pool, user, "transition", {"from": old, "to": request.target, "note": request.note})


def pool_view(db, pool, user):
    rows = members(db, pool)
    is_owner = user.id == pool.coordinator_id
    visible = rows if is_owner else [m for m in rows if m.user_id == user.id]
    snapshot = pool.locked_quote
    if snapshot and not is_owner:
        snapshot = {
            **snapshot,
            "participants": [p for p in snapshot["participants"] if p["participant_id"] == user.id],
        }
    return {
        "id": pool.id,
        "coordinator_id": pool.coordinator_id,
        "route_id": pool.route_id,
        "rate_card_id": pool.rate_card_id,
        "travel_date": pool.travel_date,
        "commodity": pool.commodity,
        "pickup_description": pool.pickup_description,
        "max_quantity_kg": pool.max_quantity_kg,
        "approved_quantity_kg": sum(m.quantity_kg for m in rows if m.status == "APPROVED"),
        "state": pool.state,
        "version": pool.version,
        "created_at": pool.created_at,
        "locked_quote": snapshot,
        "transport_reference": pool.transport_reference,
        "members": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "quantity_kg": m.quantity_kg,
                "variety": m.variety,
                "grade": m.grade,
                "condition": m.condition,
                "status": m.status,
            }
            for m in visible
        ],
    }
