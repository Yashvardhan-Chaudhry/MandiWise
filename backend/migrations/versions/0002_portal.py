"""Farmer portal accounts and membership-restricted chat."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001_transport"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transport_portal_accounts",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("transport_users.id"), primary_key=True),
        sa.Column("username", sa.String(40), nullable=False),
        sa.Column("password_hash", sa.String(250), nullable=False),
        sa.Column("village", sa.String(160), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "transport_portal_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), sa.ForeignKey("transport_pools.id"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("transport_users.id"), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_transport_portal_messages_pool_id", "transport_portal_messages", ["pool_id"]
    )


def downgrade():
    op.drop_table("transport_portal_messages")
    op.drop_table("transport_portal_accounts")
