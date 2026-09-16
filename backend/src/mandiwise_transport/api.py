import os
from importlib.resources import files
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from . import schemas as s
from . import services as svc
from .db import Location, Member, Pool, PoolEvent, RateCard, Route, User, database
from .engine import TransportError, kg
from .presentation import router as presentation_router

bearer = HTTPBearer(auto_error=False)


def session(request: Request):
    with request.app.state.sessions() as db:
        yield db


DB = Annotated[Session, Depends(session)]


def current_user(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    token = (
        credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
    )
    if not token and request.cookies.get("mandiwise_session"):
        from .portal import check_origin

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            check_origin(request)
        token = request.cookies["mandiwise_session"]
    if not token:
        raise svc.DomainError("unauthenticated", "A bearer access token is required", 401)
    try:
        claims = jwt.decode(
            token,
            request.app.state.jwt_secret,
            algorithms=["HS256"],
            audience="mandiwise-transport",
            issuer="mandiwise",
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        raise svc.DomainError("unauthenticated", "Invalid or expired access token", 401) from None
    user = db.get(User, claims["sub"])
    if user is None or not user.active:
        raise svc.DomainError("unauthenticated", "Account is inactive or unknown", 401)
    return user


Actor = Annotated[User, Depends(current_user)]


def admin(user: Actor):
    if user.role != "admin":
        raise svc.DomainError("forbidden", "Administrator access required", 403)
    return user


Admin = Annotated[User, Depends(admin)]


def commit(db):
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise svc.DomainError(
            "version_conflict", "Concurrent pool change; reload and retry"
        ) from None
    except IntegrityError:
        db.rollback()
        raise svc.DomainError("conflict", "Duplicate or invalid record") from None
    except OperationalError:
        db.rollback()
        raise svc.DomainError(
            "database_busy", "Database unavailable or busy; retry later", 503
        ) from None


def record(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def create_app(database_url=None, jwt_secret=None):
    secret = jwt_secret or os.getenv("JWT_SECRET", "")
    if len(secret.encode()) < 32:
        raise RuntimeError("Set JWT_SECRET to a random secret of at least 32 bytes")
    app = FastAPI(
        title="MandiWise Transport",
        version="0.1.0",
        description="Sourced transport estimates and identity-preserved pooling. INR and quintals.",
    )
    app.state.engine, app.state.sessions = database(database_url)
    app.state.jwt_secret = secret
    app.mount(
        "/assets",
        StaticFiles(directory=str(files("mandiwise_transport").joinpath("web/static"))),
        name="assets",
    )
    app.include_router(presentation_router)
    from .portal import router as portal_router

    app.include_router(portal_router)

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/demo")

    @app.exception_handler(svc.DomainError)
    async def domain_error(request, exc):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else {}
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=headers,
        )

    @app.exception_handler(TransportError)
    async def engine_error(request, exc):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_transport_input", "message": str(exc)}},
        )

    @app.get("/health", tags=["system"])
    def health(db: DB):
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/v1/me", tags=["identity"])
    def me(user: Actor):
        return {"id": user.id, "name": user.name, "role": user.role}

    @app.post("/v1/locations", status_code=201, tags=["catalogue"])
    def add_location(body: s.LocationInput, db: DB, user: Admin):
        row = Location(**body.model_dump())
        db.add(row)
        commit(db)
        return record(row)

    @app.get("/v1/locations", tags=["catalogue"])
    def locations(
        db: DB, user: Actor, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ):
        return [
            record(r)
            for r in db.scalars(select(Location).order_by(Location.id).offset(offset).limit(limit))
        ]

    @app.post("/v1/routes", status_code=201, tags=["catalogue"])
    def add_route(body: s.RouteInput, db: DB, user: Admin):
        svc.endpoints(db, body.origin_id, body.destination_id)
        values = body.model_dump(exclude={"distance_km"})
        row = Route(**values, distance_m=int(body.distance_km * 1000))
        db.add(row)
        commit(db)
        return record(row)

    @app.get("/v1/routes", tags=["catalogue"])
    def routes(
        db: DB,
        user: Actor,
        origin_id: str | None = None,
        destination_id: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        query = select(Route)
        if origin_id:
            query = query.where(Route.origin_id == origin_id)
        if destination_id:
            query = query.where(Route.destination_id == destination_id)
        return [record(r) for r in db.scalars(query.order_by(Route.id).offset(offset).limit(limit))]

    @app.post("/v1/rate-cards", status_code=201, tags=["catalogue"])
    def add_card(body: s.RateCardInput, db: DB, user: Admin):
        svc.endpoints(db, body.origin_id, body.destination_id)
        row = RateCard(
            **body.model_dump(exclude={"vehicles"}),
            vehicles=[v.model_dump(mode="json") for v in body.vehicles],
        )
        db.add(row)
        commit(db)
        return record(row)

    @app.get("/v1/rate-cards", tags=["catalogue"])
    def cards(
        db: DB,
        user: Actor,
        origin_id: str | None = None,
        destination_id: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        query = select(RateCard)
        if origin_id:
            query = query.where(RateCard.origin_id == origin_id)
        if destination_id:
            query = query.where(RateCard.destination_id == destination_id)
        return [
            record(r) for r in db.scalars(query.order_by(RateCard.id).offset(offset).limit(limit))
        ]

    @app.post("/v1/transport/quote", tags=["estimates"])
    def transport_quote(body: s.QuoteInput, db: DB, user: Actor):
        return svc.quote(db, body)

    @app.post("/v1/transport/pool-quote", tags=["estimates"])
    def transport_pool_quote(body: s.PoolQuoteInput, db: DB, user: Actor):
        return svc.quote(db, body)

    @app.post("/v1/pools", status_code=201, tags=["pools"])
    def create_pool(body: s.PoolInput, db: DB, user: Actor):
        if user.role != "coordinator":
            raise svc.DomainError("forbidden", "Pool coordinator permission required", 403)
        if body.travel_date < svc.today():
            raise svc.DomainError("past_trip", "Travel date must be today or later", 422)
        svc.inputs(db, body.route_id, body.rate_card_id, body.travel_date)
        row = Pool(
            **body.model_dump(exclude={"max_quantity_quintals"}),
            max_quantity_kg=kg(body.max_quantity_quintals),
            coordinator_id=user.id,
        )
        db.add(row)
        db.flush()
        db.add(PoolEvent(pool_id=row.id, actor_id=user.id, action="created", detail={}))
        commit(db)
        return svc.pool_view(db, row, user)

    @app.get("/v1/pools", tags=["pools"])
    def list_pools(
        db: DB, user: Actor, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ):
        # Discovery contains no other farmer's lot declarations or financial shares.
        return [
            {
                "id": p.id,
                "commodity": p.commodity,
                "travel_date": p.travel_date,
                "route_id": p.route_id,
                "rate_card_id": p.rate_card_id,
                "pickup_description": p.pickup_description,
                "max_quantity_kg": p.max_quantity_kg,
                "state": p.state,
            }
            for p in db.scalars(
                select(Pool)
                .where(Pool.state == "OPEN", Pool.travel_date >= svc.today())
                .order_by(Pool.travel_date, Pool.id)
                .offset(offset)
                .limit(limit)
            )
        ]

    @app.get("/v1/me/pools", tags=["pools"])
    def my_pools(
        db: DB, user: Actor, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ):
        joined = select(Member.pool_id).where(Member.user_id == user.id)
        query = select(Pool).where((Pool.coordinator_id == user.id) | Pool.id.in_(joined))
        return [
            svc.pool_view(db, p, user)
            for p in db.scalars(
                query.order_by(Pool.created_at.desc(), Pool.id).offset(offset).limit(limit)
            )
        ]

    def accessible(db, pool, user):
        if pool.coordinator_id != user.id and not db.scalar(
            select(Member.id).where(Member.pool_id == pool.id, Member.user_id == user.id)
        ):
            raise svc.DomainError(
                "forbidden", "Pool details are visible only to its participants", 403
            )

    @app.get("/v1/pools/{pool_id}", tags=["pools"])
    def pool_detail(pool_id: str, db: DB, user: Actor):
        pool = svc.get(db, Pool, pool_id)
        accessible(db, pool, user)
        return svc.pool_view(db, pool, user)

    @app.post("/v1/pools/{pool_id}/join", status_code=201, tags=["pools"])
    def join(pool_id: str, body: s.JoinInput, db: DB, user: Actor):
        if user.role not in {"farmer", "coordinator"}:
            raise svc.DomainError("forbidden", "Farmer account required", 403)
        pool = svc.get(db, Pool, pool_id)
        svc.open_pool(pool)
        rows = svc.members(db, pool)
        existing = next((m for m in rows if m.user_id == user.id), None)
        if existing and existing.status in {"PENDING", "APPROVED"}:
            raise svc.DomainError("already_joined", "Withdraw the current lot before changing it")
        if len(rows) >= 50 and existing is None:
            raise svc.DomainError("member_limit", "Pool is limited to 50 member records")
        if kg(body.quantity_quintals) > pool.max_quantity_kg:
            raise svc.DomainError("capacity_exceeded", "Lot exceeds the pool's maximum quantity")
        row = existing or Member(pool_id=pool_id, user_id=user.id)
        row.quantity_kg = kg(body.quantity_quintals)
        row.variety, row.grade, row.condition = body.variety, body.grade, body.condition
        row.status = "PENDING"
        db.add(row)
        svc.touch(
            db, pool, user, "join_requested", {"user_id": user.id, **body.model_dump(mode="json")}
        )
        commit(db)
        return svc.pool_view(db, pool, user)

    @app.post("/v1/pools/{pool_id}/members/{member_id}/review", tags=["pools"])
    def review(pool_id: str, member_id: str, body: s.ReviewInput, db: DB, user: Actor):
        pool = svc.get(db, Pool, pool_id)
        svc.manager(pool, user)
        svc.open_pool(pool)
        svc.version(pool, body.expected_version)
        member = svc.get(db, Member, member_id)
        if member.pool_id != pool.id:
            raise svc.DomainError("not_found", "Member not found in this pool", 404)
        if member.status != "PENDING":
            raise svc.DomainError("already_reviewed", "Only pending requests can be reviewed")
        if body.decision == "APPROVED":
            total = sum(m.quantity_kg for m in svc.members(db, pool) if m.status == "APPROVED")
            if total + member.quantity_kg > pool.max_quantity_kg:
                raise svc.DomainError("capacity_exceeded", "Approval would exceed pool capacity")
        member.status = body.decision
        svc.touch(
            db, pool, user, "member_reviewed", {"member_id": member.id, "status": body.decision}
        )
        commit(db)
        return svc.pool_view(db, pool, user)

    @app.post("/v1/pools/{pool_id}/withdraw", tags=["pools"])
    def withdraw(pool_id: str, body: s.VersionInput, db: DB, user: Actor):
        pool = svc.get(db, Pool, pool_id)
        svc.open_pool(pool)
        svc.version(pool, body.expected_version)
        member = db.scalar(
            select(Member).where(Member.pool_id == pool.id, Member.user_id == user.id)
        )
        if member is None or member.status not in {"PENDING", "APPROVED"}:
            raise svc.DomainError("no_membership", "No active membership to withdraw")
        member.status = "WITHDRAWN"
        svc.touch(db, pool, user, "withdrawn", {"member_id": member.id})
        commit(db)
        return svc.pool_view(db, pool, user)

    @app.post("/v1/pools/{pool_id}/quote", tags=["pools"])
    def preview(pool_id: str, db: DB, user: Actor):
        pool = svc.get(db, Pool, pool_id)
        accessible(db, pool, user)
        result = pool.locked_quote or svc.approved_quote(db, pool)
        if user.id != pool.coordinator_id:
            result = {
                **result,
                "participants": [
                    p for p in result["participants"] if p["participant_id"] == user.id
                ],
            }
        return result

    @app.post("/v1/pools/{pool_id}/transition", tags=["pools"])
    def move(pool_id: str, body: s.TransitionInput, db: DB, user: Actor):
        pool = svc.get(db, Pool, pool_id)
        svc.transition(db, pool, user, body)
        commit(db)
        return svc.pool_view(db, pool, user)

    @app.get("/v1/pools/{pool_id}/events", tags=["pools"])
    def events(
        pool_id: str,
        db: DB,
        user: Actor,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        pool = svc.get(db, Pool, pool_id)
        svc.manager(pool, user)
        return [
            record(e)
            for e in db.scalars(
                select(PoolEvent)
                .where(PoolEvent.pool_id == pool_id)
                .order_by(PoolEvent.created_at, PoolEvent.id)
                .offset(offset)
                .limit(limit)
            )
        ]

    return app
