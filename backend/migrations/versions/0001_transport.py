"""Initial transport-only schema; independent from future market-price/user schemas."""

import sqlalchemy as sa
from alembic import op

revision = "0001_transport"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transport_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("role IN ('farmer','coordinator','admin')"),
    )
    op.create_table(
        "transport_locations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("state", sa.String(160), nullable=False),
        sa.Column("district", sa.String(160), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.UniqueConstraint("name", "kind", "state", "district"),
        sa.CheckConstraint("kind IN ('origin','mandi')"),
    )
    for table in ("transport_routes", "transport_rate_cards"):
        columns = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "origin_id", sa.String(36), sa.ForeignKey("transport_locations.id"), nullable=False
            ),
            sa.Column(
                "destination_id",
                sa.String(36),
                sa.ForeignKey("transport_locations.id"),
                nullable=False,
            ),
            sa.Column("source", sa.String(500), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("effective_until", sa.Date(), nullable=False),
            sa.CheckConstraint("effective_until >= effective_from"),
        ]
        if table == "transport_routes":
            columns.extend(
                [
                    sa.Column("distance_m", sa.Integer(), nullable=False),
                    sa.CheckConstraint("distance_m > 0 AND distance_m <= 2000000"),
                ]
            )
        else:
            columns.extend(
                [
                    sa.Column("name", sa.String(160), nullable=False),
                    sa.Column("is_demo", sa.Boolean(), nullable=False),
                    sa.Column("vehicles", sa.JSON(), nullable=False),
                ]
            )
        op.create_table(table, *columns)
    op.create_table(
        "transport_pools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "coordinator_id", sa.String(36), sa.ForeignKey("transport_users.id"), nullable=False
        ),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("transport_routes.id"), nullable=False),
        sa.Column(
            "rate_card_id", sa.String(36), sa.ForeignKey("transport_rate_cards.id"), nullable=False
        ),
        sa.Column("travel_date", sa.Date(), nullable=False),
        sa.Column("commodity", sa.String(160), nullable=False),
        sa.Column("pickup_description", sa.String(500), nullable=False),
        sa.Column("max_quantity_kg", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("locked_quote", sa.JSON(), nullable=True),
        sa.Column("transport_reference", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_quantity_kg > 0 AND max_quantity_kg <= 100000"),
        sa.CheckConstraint("state IN ('OPEN','LOCKED','DISPATCHED','SETTLED','CANCELLED')"),
    )
    op.create_table(
        "transport_pool_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), sa.ForeignKey("transport_pools.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("transport_users.id"), nullable=False),
        sa.Column("quantity_kg", sa.Integer(), nullable=False),
        sa.Column("variety", sa.String(160), nullable=False),
        sa.Column("grade", sa.String(160), nullable=False),
        sa.Column("condition", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("pool_id", "user_id"),
        sa.CheckConstraint("quantity_kg > 0 AND quantity_kg <= 100000"),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')"),
    )
    op.create_table(
        "transport_pool_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), sa.ForeignKey("transport_pools.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("transport_users.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table, column in [
        ("transport_pools", "coordinator_id"),
        ("transport_pools", "travel_date"),
        ("transport_pools", "state"),
        ("transport_pool_members", "pool_id"),
        ("transport_pool_events", "pool_id"),
    ]:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in [
        "transport_pool_events",
        "transport_pool_members",
        "transport_pools",
        "transport_rate_cards",
        "transport_routes",
        "transport_locations",
        "transport_users",
    ]:
        op.drop_table(table)
