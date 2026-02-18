"""initial schema

Revision ID: 20260217_0001
Revises: None
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260217_0001"
down_revision = None
branch_labels = None
depends_on = None


role_enum = sa.Enum("CREATOR", "ADMIN", name="role")
plan_code_enum = sa.Enum("FREE", "PRO", "LIFETIME", name="plancode")
scoring_enum = sa.Enum("CLASSIC", "RASCH", name="scoringtype")
test_type_enum = sa.Enum("EXAM", "OLYMPIAD", "TEST", name="testtype")
field_type_enum = sa.Enum("TEXT", "EMAIL", "TEL", "TEXTAREA", name="fieldtype")
question_type_enum = sa.Enum("SHORT_ANSWER", "MULTIPLE_CHOICE", "ESSAY", "TRUE_FALSE", name="questiontype")
submission_status_enum = sa.Enum("PENDING_REVIEW", "COMPLETED", name="submissionstatus")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", plan_code_enum, nullable=False, unique=True),
        sa.Column("limits", sa.JSON(), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("billing_cycle", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "tests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("creator_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False),
        sa.Column("scoring_type", scoring_enum, nullable=False),
        sa.Column("test_type", test_type_enum, nullable=False),
        sa.Column("creator_plan_snapshot", plan_code_enum, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tests_creator_id", "tests", ["creator_id"], unique=False)

    op.create_table(
        "participant_fields",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("field_type", field_type_enum, nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_index("ix_participant_fields_test_id", "participant_fields", ["test_id"], unique=False)

    op.create_table(
        "questions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("q_type", question_type_enum, nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("points", sa.Float(), nullable=False),
        sa.Column("correct_answer_text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_test_id", "questions", ["test_id"], unique=False)

    op.create_table(
        "question_options",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("question_id", sa.UUID(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_index", sa.Integer(), nullable=False),
        sa.Column("option_html", sa.Text(), nullable=False),
        sa.UniqueConstraint("question_id", "option_index"),
    )
    op.create_index("ix_question_options_question_id", "question_options", ["question_id"], unique=False)

    op.create_table(
        "submissions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_full_name", sa.String(length=200), nullable=False),
        sa.Column("participant_attempt_value", sa.String(length=200), nullable=False),
        sa.Column("participant_secondary", sa.String(length=200), nullable=False),
        sa.Column("participant_fields_json", sa.JSON(), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("auto_score", sa.Float(), nullable=False),
        sa.Column("auto_max_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("status", submission_status_enum, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_submissions_test_id", "submissions", ["test_id"], unique=False)
    op.create_index("ix_submissions_status", "submissions", ["status"], unique=False)
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"], unique=False)
    op.create_index(
        "ix_submissions_participant_attempt_value",
        "submissions",
        ["participant_attempt_value"],
        unique=False,
    )

    op.create_table(
        "manual_grades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("submission_id", sa.UUID(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.UUID(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("grader_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_id", "question_id"),
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.BigInteger(), sa.ForeignKey("tests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("public_url", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(length=2048), nullable=False, unique=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("outbox_events")
    op.drop_table("audit_logs")
    op.drop_table("media_assets")
    op.drop_table("manual_grades")
    op.drop_index("ix_submissions_participant_attempt_value", table_name="submissions")
    op.drop_index("ix_submissions_submitted_at", table_name="submissions")
    op.drop_index("ix_submissions_status", table_name="submissions")
    op.drop_index("ix_submissions_test_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_question_options_question_id", table_name="question_options")
    op.drop_table("question_options")
    op.drop_index("ix_questions_test_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_participant_fields_test_id", table_name="participant_fields")
    op.drop_table("participant_fields")
    op.drop_index("ix_tests_creator_id", table_name="tests")
    op.drop_table("tests")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

