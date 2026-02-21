"""add two part written question type

Revision ID: 20260221_0002
Revises: 20260217_0001
Create Date: 2026-02-21
"""

from alembic import op


revision = "20260221_0002"
down_revision = "20260217_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'TWO_PART_WRITTEN'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place.
    pass

