"""add IRT scoring and test modules

Revision ID: 20261124_0005
Revises: 20260409_0004
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261124_0005"
down_revision = "20260409_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE scoringtype ADD VALUE IF NOT EXISTS 'IRT'")
    op.add_column("tests", sa.Column("modules_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.alter_column("tests", "modules_json", server_default=None)
    op.add_column("questions", sa.Column("module_id", sa.String(length=64), nullable=True))
    op.add_column("questions", sa.Column("difficulty", sa.Float(), nullable=False, server_default="0"))
    op.add_column("questions", sa.Column("discrimination", sa.Float(), nullable=False, server_default="1"))
    op.add_column("questions", sa.Column("guessing", sa.Float(), nullable=False, server_default="0"))
    op.alter_column("questions", "difficulty", server_default=None)
    op.alter_column("questions", "discrimination", server_default=None)
    op.alter_column("questions", "guessing", server_default=None)


def downgrade() -> None:
    op.drop_column("questions", "guessing")
    op.drop_column("questions", "discrimination")
    op.drop_column("questions", "difficulty")
    op.drop_column("questions", "module_id")
    op.drop_column("tests", "modules_json")
