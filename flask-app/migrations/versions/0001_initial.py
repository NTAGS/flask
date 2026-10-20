"""initial commerce schema

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_product_category", "product", ["category"], unique=False)

    op.create_table(
        "order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index("ix_order_order_number", "order", ["order_number"], unique=False)
    op.create_index("ix_order_username", "order", ["username"], unique=False)
    op.create_index("ix_order_status", "order", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_order_status", table_name="order")
    op.drop_index("ix_order_username", table_name="order")
    op.drop_index("ix_order_order_number", table_name="order")
    op.drop_table("order")
    op.drop_index("ix_product_category", table_name="product")
    op.drop_table("product")
