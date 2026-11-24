"""add SAT math grid-in question type

Revision ID: 20261124_0007
Revises: 20261124_0006
Create Date: 2026-11-24
"""

from alembic import op


revision = "20261124_0007"
down_revision = "20261124_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'SAT_MATH_INPUT'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place.
    pass
