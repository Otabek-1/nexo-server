"""add two part math question type

Revision ID: 20260409_0004
Revises: 20260221_0003
Create Date: 2026-04-09
"""

from alembic import op


revision = "20260409_0004"
down_revision = "20260221_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'TWO_PART_MATH'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place.
    pass
