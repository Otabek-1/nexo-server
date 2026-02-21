"""attempts toggle and telegram registrations

Revision ID: 20260221_0003
Revises: 20260221_0002
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_0003"
down_revision = "20260221_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'TWO_PART_WRITTEN'")

    op.add_column("tests", sa.Column("attempts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tests", sa.Column("registration_window_hours", sa.Integer(), nullable=True))
    op.alter_column("tests", "attempts_enabled", server_default=None)

    op.create_table(
        "test_registrations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone_e164", sa.String(length=20), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=120), nullable=True),
        sa.Column("telegram_full_name", sa.String(length=200), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("test_id", "phone_e164"),
        sa.UniqueConstraint("test_id", "telegram_user_id"),
    )
    op.create_index("ix_test_registrations_test_id", "test_registrations", ["test_id"], unique=False)

    op.create_table(
        "telegram_registration_states",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_telegram_registration_states_test_id",
        "telegram_registration_states",
        ["test_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_registration_states_test_id", table_name="telegram_registration_states")
    op.drop_table("telegram_registration_states")

    op.drop_index("ix_test_registrations_test_id", table_name="test_registrations")
    op.drop_table("test_registrations")

    op.drop_column("tests", "registration_window_hours")
    op.drop_column("tests", "attempts_enabled")
