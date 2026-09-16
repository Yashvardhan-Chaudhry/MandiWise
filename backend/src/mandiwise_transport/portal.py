"""Saved farmer discovery, password sign-in and membership-restricted chat."""

import hashlib
import hmac
import secrets
import threading
import time
from datetime import date
from decimal import Decimal
from importlib.resources import files
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from . import services as svc
from .api import DB, Actor, commit
from .cli import issue_token
from .db import (
    Location,
    Member,
    Pool,
    PoolEvent,
    PortalAccount,
    PortalMessage,
    RateCard,
    Route,
    User,
)
from .engine import kg
from .schemas import Input, JoinInput, Quantity, Text, VehicleInput

router = APIRouter(tags=["farmer portal"])
_lock = threading.Lock()
_attempts = {}


def check_origin(request):
    origin = request.headers.get("origin")
    if request.headers.get("X-MandiWise-Request") != "portal" or (
        origin and origin != str(request.base_url).rstrip("/")
    ):
        raise svc.DomainError("bad_origin", "Open the portal on this server and retry", 403)


def throttle(request, category, maximum=10):
    key = (category, request.client.host if request.client else "unknown")
    now = time.monotonic()
    with _lock:
        for expired in [k for k, v in _attempts.items() if now - v[0] > 60]:
            del _attempts[expired]
        start, count = _attempts.get(key, (now, 0))
        if count >= maximum or len(_attempts) > 10000:
            raise svc.DomainError("slow_down", "Too many attempts. Try again in a minute.", 429)
        _attempts[key] = (start, count + 1)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=128 * 1024 * 1024
    ).hex()
    return f"scrypt${salt}${digest}"


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, Field(pattern=r"^[a-z0-9_]{3,40}$")]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class Registration(Credentials):
    name: Text
    village: Text
    password: Annotated[str, Field(min_length=15, max_length=128)]

    @model_validator(mode="after")
    def nonblank(self):
        self.name, self.village = self.name.strip(), self.village.strip()
        if not self.name or not self.village:
            raise ValueError("Enter your name and village")
        return self


def signed_in(response, request, user):
    response.set_cookie(
        "mandiwise_session",
        issue_token(user.id, request.app.state.jwt_secret, 12),
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=43200,
        path="/",
    )
    return {"id": user.id, "name": user.name}


@router.get("/pooling", response_class=HTMLResponse, include_in_schema=False)
def page():
    return (
        files("mandiwise_transport")
        .joinpath("web/templates/pooling.html")
        .read_text(encoding="utf-8")
    )


@router.post("/portal/api/register", status_code=201)
def register(body: Registration, request: Request, response: Response, db: DB):
    check_origin(request)
    throttle(request, "auth")
    user = User(name=body.name, role="coordinator")
    db.add(user)
    db.flush()
    db.add(
        PortalAccount(
            user_id=user.id,
            username=body.username,
            village=body.village,
            password_hash=password_hash(body.password),
        )
    )
    commit(db)
    return signed_in(response, request, user)


@router.post("/portal/api/login")
def login(body: Credentials, request: Request, response: Response, db: DB):
    check_origin(request)
    throttle(request, "auth")
    account = db.scalar(select(PortalAccount).where(PortalAccount.username == body.username))
    salt = account.password_hash.split("$")[1] if account else "0" * 32
    calculated = password_hash(body.password, salt)
    user = db.get(User, account.user_id) if account else None
    if not account or not hmac.compare_digest(calculated, account.password_hash) or not user.active:
        raise svc.DomainError("login_failed", "Incorrect username or password", 401)
    return signed_in(response, request, user)


@router.post("/portal/api/logout")
def logout(request: Request, response: Response):
    check_origin(request)
    response.delete_cookie("mandiwise_session", path="/")
    return {"ok": True}


class Trip(Input):
    origin: Text
    destination: Text
    state: Text
    district: Text
    travel_date: date
    commodity: Text
    pickup_description: Annotated[str, Field(min_length=1, max_length=500)]
    distance_km: Annotated[Decimal, Field(gt=0, le=2000, decimal_places=3)]
    max_quantity_quintals: Quantity
    lot: JoinInput
    vehicles: Annotated[list[VehicleInput], Field(min_length=1, max_length=12)]

    @model_validator(mode="after")
    def limits(self):
        if self.travel_date < svc.today():
            raise ValueError("Choose today or a future travel date")
        if self.lot.quantity_quintals > self.max_quantity_quintals:
            raise ValueError("Your lot cannot exceed the group's maximum load")
        if len({v.code for v in self.vehicles}) != len(self.vehicles):
            raise ValueError("Vehicle names must be unique")
        return self


def summary(db, pool):
    route = db.get(Route, pool.route_id)
    rows = svc.members(db, pool)
    approved = [m for m in rows if m.status == "APPROVED"]
    card = db.get(RateCard, pool.rate_card_id)
    return {
        "id": pool.id,
        "origin": db.get(Location, route.origin_id).name,
        "destination": db.get(Location, route.destination_id).name,
        "district": db.get(Location, route.origin_id).district,
        "state_name": db.get(Location, route.origin_id).state,
        "organizer": db.get(User, pool.coordinator_id).name,
        "organizer_id": pool.coordinator_id,
        "travel_date": pool.travel_date,
        "commodity": pool.commodity,
        "pickup_description": pool.pickup_description,
        "state": pool.state,
        "distance_km": route.distance_m / 1000,
        "max_quantity_kg": pool.max_quantity_kg,
        "approved_quantity_kg": sum(m.quantity_kg for m in approved),
        "farmer_count": len(approved),
        "vehicles": card.vehicles,
        "rates_notice": "Organizer-entered estimate; confirm rates and availability. Not a booking.",
    }


@router.get("/portal/api/trips")
def trips(
    db: DB,
    search: str = Query("", max_length=160),
    travel_date: date | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
):
    query = (
        select(Pool)
        .join(Route, Pool.route_id == Route.id)
        .join(Location, Route.origin_id == Location.id)
    )
    query = query.where(Pool.state == "OPEN", Pool.travel_date >= svc.today())
    if travel_date:
        query = query.where(Pool.travel_date == travel_date)
    if search.strip():
        matching_destinations = select(Location.id).where(
            Location.name.icontains(search.strip(), autoescape=True)
        )
        query = query.where(
            Location.name.icontains(search.strip(), autoescape=True)
            | Location.district.icontains(search.strip(), autoescape=True)
            | Pool.commodity.icontains(search.strip(), autoescape=True)
            | Route.destination_id.in_(matching_destinations)
        )
    return [
        summary(db, p)
        for p in db.scalars(query.order_by(Pool.travel_date, Pool.id).offset(offset).limit(limit))
    ]


@router.get("/portal/api/mine")
def mine(db: DB, user: Actor):
    joined = select(Member.pool_id).where(Member.user_id == user.id)
    query = select(Pool).where((Pool.coordinator_id == user.id) | Pool.id.in_(joined))
    return [summary(db, p) for p in db.scalars(query.order_by(Pool.created_at.desc()).limit(100))]


@router.post("/portal/api/trips", status_code=201)
def post_trip(body: Trip, request: Request, db: DB, user: Actor):
    throttle(request, "create", 20)
    if user.role not in {"farmer", "coordinator"}:
        raise svc.DomainError("forbidden", "Farmer account required", 403)
    source = "Organizer-entered transport estimate; unverified supplier rates and distance"
    locations = []
    for kind, name in [("origin", body.origin), ("mandi", body.destination)]:
        location = db.scalar(
            select(Location).where(
                Location.name == name,
                Location.kind == kind,
                Location.state == body.state,
                Location.district == body.district,
            )
        )
        if not location:
            location = Location(
                name=name, kind=kind, state=body.state, district=body.district, source=source
            )
            db.add(location)
            db.flush()
        locations.append(location)
    common = dict(
        origin_id=locations[0].id,
        destination_id=locations[1].id,
        source=source,
        effective_from=body.travel_date,
        effective_until=body.travel_date,
    )
    route = Route(**common, distance_m=int(body.distance_km * 1000))
    card = RateCard(
        **common,
        name="Farmer-entered trip rates",
        is_demo=False,
        vehicles=[v.model_dump(mode="json") for v in body.vehicles],
    )
    db.add_all([route, card])
    db.flush()
    pool = Pool(
        coordinator_id=user.id,
        route_id=route.id,
        rate_card_id=card.id,
        travel_date=body.travel_date,
        commodity=body.commodity,
        pickup_description=body.pickup_description,
        max_quantity_kg=kg(body.max_quantity_quintals),
    )
    db.add(pool)
    db.flush()
    db.add(
        Member(
            pool_id=pool.id,
            user_id=user.id,
            quantity_kg=kg(body.lot.quantity_quintals),
            variety=body.lot.variety,
            grade=body.lot.grade,
            condition=body.lot.condition,
            status="APPROVED",
        )
    )
    db.add(
        PoolEvent(
            pool_id=pool.id,
            actor_id=user.id,
            action="portal_created",
            detail={"own_lot_approved": True},
        )
    )
    commit(db)
    return summary(db, pool)


@router.get("/portal/api/trips/{pool_id}")
def trip_detail(pool_id: str, db: DB):
    return summary(db, svc.get(db, Pool, pool_id))


@router.get("/portal/api/trips/{pool_id}/workspace")
def workspace(pool_id: str, db: DB, user: Actor):
    pool = svc.get(db, Pool, pool_id)
    if pool.coordinator_id != user.id and not db.scalar(
        select(Member.id).where(Member.pool_id == pool.id, Member.user_id == user.id)
    ):
        return {"id": pool.id, "version": pool.version, "members": []}
    view = svc.pool_view(db, pool, user)
    for member in view["members"]:
        member["name"] = db.get(User, member["user_id"]).name
    return view


def chat_access(db, pool_id, user):
    pool = svc.get(db, Pool, pool_id)
    member = db.scalar(
        select(Member).where(
            Member.pool_id == pool_id, Member.user_id == user.id, Member.status == "APPROVED"
        )
    )
    if pool.coordinator_id != user.id and not member:
        raise svc.DomainError(
            "forbidden", "Group chat opens after your join request is approved", 403
        )
    return pool


class Message(Input):
    body: Annotated[str, Field(min_length=1, max_length=1000)]


@router.get("/portal/api/trips/{pool_id}/messages")
def messages(pool_id: str, db: DB, user: Actor):
    chat_access(db, pool_id, user)
    rows = list(
        db.scalars(
            select(PortalMessage)
            .where(PortalMessage.pool_id == pool_id)
            .order_by(PortalMessage.created_at.desc(), PortalMessage.id.desc())
            .limit(100)
        )
    )
    return [
        {
            "id": m.id,
            "name": db.get(User, m.author_id).name,
            "body": m.body,
            "created_at": m.created_at,
        }
        for m in reversed(rows)
    ]


@router.post("/portal/api/trips/{pool_id}/messages", status_code=201)
def send_message(pool_id: str, body: Message, request: Request, db: DB, user: Actor):
    pool = chat_access(db, pool_id, user)
    if pool.state in {"CANCELLED", "SETTLED"}:
        raise svc.DomainError("closed", "This trip is closed; chat is read-only")
    throttle(request, "chat", 60)
    db.add(PortalMessage(pool_id=pool_id, author_id=user.id, body=body.body))
    commit(db)
    return {"ok": True}
