from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from mandiwise_transport.cli import seed_markets
from mandiwise_transport.db import Base


def test_migrate_seed_and_metadata(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with Session(engine) as db:
        source = Path(__file__).parents[2] / "data"
        first = seed_markets(db, source)
        second = seed_markets(db, source)
        assert first["added"] > 0
        assert second["added"] == 0
        assert first["distinct_source_markets"] == second["distinct_source_markets"]
    command.downgrade(config, "base")
    assert "transport_pools" not in inspect(engine).get_table_names()
    engine.dispose()
