"""Versioned PostgreSQL migrations; never replay old business-rule migrations."""
import argparse
from pathlib import Path

from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import Course, Period, Selection, Student, User  # noqa: F401


MIGRATIONS = sorted(Path(__file__).with_name("migrations").glob("[0-9][0-9][0-9]_*.sql"))


def apply_sql(connection, path):
    sql = path.read_text(encoding="utf-8").strip()
    if sql.startswith("BEGIN;"):
        sql = sql[len("BEGIN;"):]
    if sql.rstrip().endswith("COMMIT;"):
        sql = sql.rstrip()[:-len("COMMIT;")]
    connection.exec_driver_sql(sql)


def upgrade(*, baseline=None, initialize=False):
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Production schema initialization requires PostgreSQL")
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(20260917)"))
        tables = inspect(connection).get_table_names()
        existing = "users" in tables
        tracked = "schema_migrations" in tables
        if not existing and set(tables).intersection({"courses", "students", "selections", "periods"}):
            raise RuntimeError("Partial application schema found; repair or migrate it explicitly, do not initialize")
        if existing and not tracked and not baseline:
            raise RuntimeError("Existing untracked database: back up and specify --baseline 004 only if migrations 001-004 were already applied")
        if not existing:
            if not initialize:
                raise RuntimeError("Empty database: run python init_db.py first")
            Base.metadata.create_all(connection)
            baseline = "004"
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(3) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        if baseline:
            if tracked:
                raise RuntimeError("Baseline is only permitted for an untracked database")
            for path in MIGRATIONS:
                version = path.name[:3]
                if version <= baseline:
                    connection.execute(text("INSERT INTO schema_migrations(version) VALUES (:version)"), {"version": version})
        applied = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        for path in MIGRATIONS:
            version = path.name[:3]
            if version not in applied:
                apply_sql(connection, path)
                connection.execute(text("INSERT INTO schema_migrations(version) VALUES (:version)"), {"version": version})
                print(f"applied {path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", choices=[path.name[:3] for path in MIGRATIONS])
    args = parser.parse_args()
    upgrade(baseline=args.baseline)
