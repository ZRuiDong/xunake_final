"""Generate test-only accounts/tokens. Refuses non-empty/non-loadtest databases."""
import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import inspect
from app.database import SessionLocal, engine
from app.auth.security import create_token, hash_password
from app.models import Course, Period, Student, User
from app.utils.period import app_now
from migrate import upgrade


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-loadtest", action="store_true")
    parser.add_argument("--students", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("accounts.local.json"))
    args = parser.parse_args()
    if not args.confirm_loadtest or not (engine.url.database or "").endswith("_loadtest"):
        raise SystemExit("Requires --confirm-loadtest and database name ending in _loadtest")
    if not 3 <= args.students <= 10000:
        raise SystemExit("Student count must be between 3 and 10000")
    if args.output.exists():
        raise SystemExit("Output already exists; refusing to overwrite tokens")
    existing = inspect(engine).has_table("users")
    if existing:
        with SessionLocal() as db:
            if db.query(User).count() or db.query(Period).count() or db.query(Course).count():
                raise SystemExit("Requires an empty test database; no data was changed")
    upgrade(initialize=True)
    accounts = []
    with SessionLocal() as db:
        period = Period(name="LOAD TEST ONLY", status="ACTIVE",
            start_time=app_now()-timedelta(minutes=1), end_time=app_now()+timedelta(hours=6))
        db.add(period)
        db.flush()
        courses = [Course(name=f"Load course {i}", capacity=100, period_id=period.id) for i in range(12)]
        db.add_all(courses)
        db.flush()
        course_ids = [course.id for course in courses]
        password_hash = hash_password("LOAD-TEST-ONLY-not-for-production")
        for i in range(args.students):
            user = User(username=f"LOAD{i:05}", password_hash=password_hash,
                        role="STUDENT", must_change_password=False)
            db.add(user)
            db.flush()
            db.add(Student(user_id=user.id, student_no=user.username,
                           name=f"Load student {i}"))
            accounts.append({"username": user.username, "token": create_token(user)})
        db.commit()
    # Runtime fixture, contains authentication tokens. Exclusive creation protects
    # existing fixtures; do not commit/share this file or generate it in production.
    with args.output.open("x", encoding="utf-8") as output:
        json.dump({"course_ids": course_ids, "accounts": accounts}, output)
    args.output.chmod(0o600)
    print(f"Created {len(accounts)} test accounts; tokens expire after the configured token lifetime")
