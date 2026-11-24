from types import SimpleNamespace

from app.db import migration_bootstrap


class FakeInspector:
    def __init__(self, columns):
        self.columns = columns

    def get_table_names(self):
        return list(self.columns)

    def get_columns(self, table):
        return [{"name": column} for column in self.columns[table]]


class FakeConnection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, enum_values):
        self.enum_values = enum_values

    def execute(self, _query):
        return SimpleNamespace(
            all=lambda: [
                (enum_name, enum_value)
                for enum_name, values in self.enum_values.items()
                for enum_value in values
            ]
        )


def build_legacy_schema():
    columns = {
        table: set(required)
        for table, required in migration_bootstrap.REQUIRED_TABLE_COLUMNS.items()
    }
    enum_values = {
        enum_name: set(required)
        for enum_name, required in migration_bootstrap.REQUIRED_ENUM_VALUES.items()
    }
    return columns, enum_values


def test_detects_legacy_schema_at_known_baseline(monkeypatch):
    columns, enum_values = build_legacy_schema()
    monkeypatch.setattr(migration_bootstrap, "inspect", lambda _connection: FakeInspector(columns))

    assert migration_bootstrap.has_unversioned_legacy_schema(FakeConnection(enum_values))


def test_does_not_stamp_schema_with_post_baseline_columns(monkeypatch):
    columns, enum_values = build_legacy_schema()
    columns["tests"].add("modules_json")
    monkeypatch.setattr(migration_bootstrap, "inspect", lambda _connection: FakeInspector(columns))

    assert not migration_bootstrap.has_unversioned_legacy_schema(FakeConnection(enum_values))


def test_does_not_stamp_incomplete_schema(monkeypatch):
    columns, enum_values = build_legacy_schema()
    columns.pop("test_registrations")
    monkeypatch.setattr(migration_bootstrap, "inspect", lambda _connection: FakeInspector(columns))

    assert not migration_bootstrap.has_unversioned_legacy_schema(FakeConnection(enum_values))
