"""Optional real PostgreSQL test, using a fresh, isolated schema each run."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from mandiwise_transport.db import Base, Location, Pool, RateCard, Route, User
from mandiwise_transport.services import today


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not configured")
def test_postgres_migration_json_and_concurrent_pool_update(monkeypatch):
    base_url = os.environ["TEST_POSTGRES_URL"]
    admin_engine = create_engine(base_url)
    schema = "transport_test_" + uuid4().hex
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(base_url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    try:
        monkeypatch.setenv("DATABASE_URL", scoped.render_as_string(hide_password=False))
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        with Session(engine) as db:
            user = User(name="Test", role="coordinator")
            origin = Location(
                name="Test origin", kind="origin", state="Punjab", district="Patiala", source="test"
            )
            dest = Location(
                name="Test mandi", kind="mandi", state="Punjab", district="Patiala", source="test"
            )
            db.add_all([user, origin, dest])
            db.flush()
            common = {
                "origin_id": origin.id,
                "destination_id": dest.id,
                "source": "test",
                "effective_from": today(),
                "effective_until": today(),
            }
            route = Route(**common, distance_m=1000)
            card = RateCard(**common, name="Test", is_demo=True, vehicles=[])
            db.add_all([route, card])
            db.flush()
            p = Pool(
                coordinator_id=user.id,
                route_id=route.id,
                rate_card_id=card.id,
                travel_date=today(),
                commodity="Potato",
                pickup_description="Test",
                max_quantity_kg=100,
                locked_quote={"cost_inr": "1.01"},
            )
            db.add(p)
            db.flush()
            pool_id = p.id
            db.commit()
        with Session(engine) as a, Session(engine) as b:
            first, second = a.get(Pool, pool_id), b.get(Pool, pool_id)
            assert first.locked_quote == {"cost_inr": "1.01"}
            first.version += 1
            a.commit()
            second.version += 1
            with pytest.raises(StaleDataError):
                b.commit()
    finally:
        engine.dispose()
        # Only the exact random test schema created above is removed.
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
