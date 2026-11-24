from sqlalchemy import inspect, text

LEGACY_BASELINE_REVISION = "20260409_0004"

REQUIRED_TABLE_COLUMNS = {
    "users": {"id", "email", "role"},
    "plans": {"id", "code"},
    "subscriptions": {"id", "user_id", "plan_id"},
    "tests": {
        "id",
        "creator_id",
        "attempts_enabled",
        "registration_window_hours",
    },
    "participant_fields": {"id", "test_id", "field_key"},
    "questions": {"id", "test_id", "q_type", "correct_answer_text"},
    "question_options": {"id", "question_id", "option_index"},
    "submissions": {"id", "test_id", "answers_json", "idempotency_key"},
    "manual_grades": {"id", "submission_id", "question_id"},
    "media_assets": {"id", "owner_id", "object_key"},
    "audit_logs": {"id", "action", "entity_type"},
    "outbox_events": {"id", "event_type", "payload_json"},
    "refresh_tokens": {"id", "user_id", "token", "expires_at"},
    "test_registrations": {"id", "test_id", "phone_e164"},
    "telegram_registration_states": {"telegram_user_id", "test_id"},
}

REQUIRED_ENUM_VALUES = {
    "role": {"CREATOR", "ADMIN"},
    "plancode": {"FREE", "PRO", "LIFETIME"},
    "scoringtype": {"CLASSIC", "RASCH"},
    "testtype": {"EXAM", "OLYMPIAD", "TEST"},
    "fieldtype": {"TEXT", "EMAIL", "TEL", "TEXTAREA"},
    "questiontype": {
        "SHORT_ANSWER",
        "MULTIPLE_CHOICE",
        "ESSAY",
        "TRUE_FALSE",
        "TWO_PART_WRITTEN",
        "TWO_PART_MATH",
    },
    "submissionstatus": {"PENDING_REVIEW", "COMPLETED"},
}


def has_unversioned_legacy_schema(connection) -> bool:
    if connection.dialect.name != "postgresql":
        return False

    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if not set(REQUIRED_TABLE_COLUMNS).issubset(tables):
        return False

    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        columns = {column["name"] for column in inspector.get_columns(table)}
        if not required_columns.issubset(columns):
            return False

    enum_rows = connection.execute(
        text(
            "SELECT t.typname, e.enumlabel "
            "FROM pg_type AS t "
            "JOIN pg_enum AS e ON t.oid = e.enumtypid "
            "JOIN pg_namespace AS n ON n.oid = t.typnamespace "
            "WHERE n.nspname = current_schema()"
        )
    ).all()
    enum_values: dict[str, set[str]] = {}
    for enum_name, enum_value in enum_rows:
        enum_values.setdefault(enum_name, set()).add(enum_value)

    if any(
        not required.issubset(enum_values.get(enum_name, set()))
        for enum_name, required in REQUIRED_ENUM_VALUES.items()
    ):
        return False

    later_schema_markers = {
        "tests": {"modules_json"},
        "questions": {"module_id", "difficulty", "discrimination", "guessing"},
        "submissions": {"result_notified_at"},
    }
    for table, columns_after_baseline in later_schema_markers.items():
        columns = {column["name"] for column in inspector.get_columns(table)}
        if columns & columns_after_baseline:
            return False

    if "SAT" in enum_values.get("testtype", set()):
        return False
    return "SAT_MATH_INPUT" not in enum_values.get("questiontype", set())
