"""Run the opt-in PostgreSQL suite from container connection settings."""
import os
import sys
import unittest
from pathlib import Path

from sqlalchemy.engine import URL


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD must be set")

    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("POSTGRES_USER", "course_admin"),
        password=password,
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "course_system"),
    )
    os.environ["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
    suite = unittest.defaultTestLoader.discover(
        "tests",
        pattern="test_postgres_concurrency.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
