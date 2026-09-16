import os
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "transport_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('farmer','coordinator','admin')"),)


class PortalAccount(Base):
    __tablename__ = "transport_portal_accounts"
    user_id: Mapped[str] = mapped_column(ForeignKey(User.id), primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(250))
    village: Mapped[str] = mapped_column(String(160))


class PortalMessage(Base):
    __tablename__ = "transport_portal_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    pool_id: Mapped[str] = mapped_column(ForeignKey("transport_pools.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey(User.id))
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Location(Base):
    __tablename__ = "transport_locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(160))
    district: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("name", "kind", "state", "district"),
        CheckConstraint("kind IN ('origin','mandi')"),
    )


class Route(Base):
    __tablename__ = "transport_routes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    origin_id: Mapped[str] = mapped_column(ForeignKey(Location.id))
    destination_id: Mapped[str] = mapped_column(ForeignKey(Location.id))
    distance_m: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(500))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date] = mapped_column(Date)
    __table_args__ = (
        CheckConstraint("distance_m > 0 AND distance_m <= 2000000"),
        CheckConstraint("effective_until >= effective_from"),
    )


class RateCard(Base):
    __tablename__ = "transport_rate_cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    origin_id: Mapped[str] = mapped_column(ForeignKey(Location.id))
    destination_id: Mapped[str] = mapped_column(ForeignKey(Location.id))
    source: Mapped[str] = mapped_column(String(500))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date] = mapped_column(Date)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    vehicles: Mapped[list] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("effective_until >= effective_from"),)


class Pool(Base):
    __tablename__ = "transport_pools"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    coordinator_id: Mapped[str] = mapped_column(ForeignKey(User.id), index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey(Route.id))
    rate_card_id: Mapped[str] = mapped_column(ForeignKey(RateCard.id))
    travel_date: Mapped[date] = mapped_column(Date, index=True)
    commodity: Mapped[str] = mapped_column(String(160))
    pickup_description: Mapped[str] = mapped_column(String(500))
    max_quantity_kg: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    locked_quote: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transport_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        CheckConstraint("max_quantity_kg > 0 AND max_quantity_kg <= 100000"),
        CheckConstraint("state IN ('OPEN','LOCKED','DISPATCHED','SETTLED','CANCELLED')"),
    )


class Member(Base):
    __tablename__ = "transport_pool_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    pool_id: Mapped[str] = mapped_column(ForeignKey(Pool.id), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey(User.id))
    quantity_kg: Mapped[int] = mapped_column(Integer)
    variety: Mapped[str] = mapped_column(String(160))
    grade: Mapped[str] = mapped_column(String(160))
    condition: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    __table_args__ = (
        UniqueConstraint("pool_id", "user_id"),
        CheckConstraint("quantity_kg > 0 AND quantity_kg <= 100000"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')"),
    )


class PoolEvent(Base):
    __tablename__ = "transport_pool_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    pool_id: Mapped[str] = mapped_column(ForeignKey(Pool.id), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey(User.id))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def database(url=None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./transport.db")
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 10}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_fk(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(engine, expire_on_commit=False)
