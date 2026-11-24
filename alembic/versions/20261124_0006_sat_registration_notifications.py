"""require Telegram registration for SAT tests and track score notifications

Revision ID: 20261124_0006
Revises: 20261124_0005
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20261124_0006"
down_revision = "20261124_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE testtype ADD VALUE IF NOT EXISTS 'SAT'")
    op.add_column(
        "submissions",
        sa.Column("result_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submissions", "result_notified_at")
    # PostgreSQL enum values cannot be removed safely in-place.
