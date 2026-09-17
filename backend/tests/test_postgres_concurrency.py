"""Opt-in tests in a newly created private PostgreSQL schema, never user tables."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from time import monotonic
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Course, Period, Selection, Student, User
from app.student.router import select_course, cancel_course
from app.course.router import update_course
from app.course.schema import CourseCreate
from app.admin.router import finalize_period
from app.utils.period import app_now, get_locked_active_period
from datetime import timedelta
from migrate import apply_sql
import migrate


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to opt in to isolated PostgreSQL tests")
class PostgreSQLConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.schema = "test_selection_" + uuid4().hex
        self.control = create_engine(os.environ["TEST_DATABASE_URL"])
        with self.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_engine(os.environ["TEST_DATABASE_URL"], pool_size=12,
            max_overflow=0, connect_args={"options": f"-c search_path={self.schema} -c lock_timeout=5000 -c statement_timeout=10000"})
        self.Session = sessionmaker(bind=self.engine)
        with self.engine.begin() as connection:
            Base.metadata.create_all(connection)
            apply_sql(connection, Path(__file__).parents[1] / "migrations/005_concurrency_guards.sql")
        with self.Session() as db:
            period = Period(name="concurrency", start_time=app_now()-timedelta(hours=1),
                            end_time=app_now()+timedelta(hours=1), status="ACTIVE")
            db.add(period)
            db.flush()
            self.period_id = period.id
            courses = [Course(name=f"C{i}", capacity=2, period_id=period.id) for i in range(3)]
            db.add_all(courses)
            db.flush()
            self.course_ids = [c.id for c in courses]
            self.student_ids = []
            for i in range(12):
                user = User(username=f"S{i}", password_hash="unused", role="STUDENT")
                db.add(user)
                db.flush()
                student = Student(user_id=user.id, student_no=user.username,
                                  name=user.username, weight=i)
                db.add(student)
                db.flush()
                self.student_ids.append(student.id)
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        # The identifier was generated here (not supplied by an environment variable).
        if not self.schema.startswith("test_selection_") or len(self.schema) != 47:
            raise RuntimeError("Refusing unsafe schema cleanup")
        with self.control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.control.dispose()

    def choose(self, student, course):
        with self.Session() as db:
            try:
                return select_course(course, db=db, username=f"S{student}")["status"]
            except HTTPException as error:
                return error.status_code

    def test_different_courses_can_write_while_stage_share_lock_is_held(self):
        with self.Session() as held:
            self.assertIsNotNone(get_locked_active_period(held))
            with ThreadPoolExecutor(max_workers=1) as executor:
                # An exclusive stage lock would block until the 5s lock timeout.
                result = executor.submit(self.choose, 1, self.course_ids[1]).result(timeout=3)
            self.assertEqual(result, "SELECTED")
            held.rollback()

    def test_parallel_three_choices_cannot_exceed_two(self):
        barrier = Barrier(3)
        def run(course):
            barrier.wait(timeout=5)
            return self.choose(0, course)
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(run, self.course_ids))
        self.assertEqual(results.count(400), 1)
        with self.Session() as db:
            self.assertEqual(db.query(Selection).count(), 2)

    def test_database_trigger_rejects_a_third_direct_insert(self):
        with self.Session() as db:
            for course in self.course_ids[:2]:
                db.add(Selection(student_id=self.student_ids[0], course_id=course,
                                 period_id=self.period_id, status="WAITING"))
                db.commit()
            db.add(Selection(student_id=self.student_ids[0], course_id=self.course_ids[2],
                             period_id=self.period_id, status="WAITING"))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

    def test_direct_parallel_inserts_also_obey_the_database_limit(self):
        barrier = Barrier(3)
        def insert(course):
            with self.Session() as db:
                db.add(Selection(student_id=self.student_ids[0], course_id=course,
                                 period_id=self.period_id, status="WAITING"))
                barrier.wait(timeout=5)
                try:
                    db.commit()
                    return True
                except IntegrityError:
                    db.rollback()
                    return False
        with ThreadPoolExecutor(max_workers=3) as executor:
            self.assertEqual(list(executor.map(insert, self.course_ids)).count(True), 2)
        with self.Session() as db:
            self.assertEqual(db.query(Selection).count(), 2)

    def test_fresh_initialization_installs_guards_and_is_repeatable(self):
        Base.metadata.drop_all(self.engine)
        with patch.object(migrate, "engine", self.engine):
            migrate.upgrade(initialize=True)
            migrate.upgrade(initialize=True)
        with self.engine.connect() as connection:
            versions = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
            self.assertEqual(versions, {"001", "002", "003", "004", "005", "006"})
            self.assertEqual(connection.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname='trg_student_selection_limit' AND tgrelid='selections'::regclass")).scalar(), 1)
            self.assertIsNotNone(connection.execute(text("SELECT to_regclass('uq_periods_single_open')")).scalar())
            self.assertIsNotNone(connection.execute(text("SELECT to_regclass('audit_logs')")).scalar())

    def test_migrations_are_not_replayed_after_enabling_two_courses(self):
        self.choose(0, self.course_ids[0])
        self.choose(0, self.course_ids[1])
        with patch.object(migrate, "engine", self.engine):
            migrate.upgrade(baseline="004")
            migrate.upgrade()
        with self.Session() as db:
            self.assertEqual(db.query(Selection).count(), 2)

    def test_hot_course_has_correct_weight_ranking_without_over_enrollment(self):
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda i: self.choose(i, self.course_ids[0]), range(12)))
        self.assertTrue(all(result in ("SELECTED", "WAITING") for result in results))
        with self.Session() as db:
            winners = db.query(Selection).filter(Selection.status == "SELECTED").all()
            self.assertEqual({s.student_id for s in winners}, set(self.student_ids[-2:]))
            self.assertEqual(db.query(Selection).count(), 12)

    def test_capacity_reranking_does_not_lock_other_students(self):
        self.choose(0, self.course_ids[0])
        self.choose(1, self.course_ids[0])
        with self.Session() as held:
            get_locked_active_period(held)
            held.query(Student).filter(Student.id == self.student_ids[0]).with_for_update().first()
            def resize():
                with self.Session() as db:
                    return update_course(self.course_ids[0], CourseCreate(name="C0", capacity=1),
                                         db=db, admin="admin")
            with ThreadPoolExecutor(max_workers=1) as executor:
                self.assertEqual(executor.submit(resize).result(timeout=3)["message"], "course updated")
            held.rollback()

    def test_closing_waits_for_inflight_selection_then_finalizes_it(self):
        self.choose(0, self.course_ids[0])
        started = Event()
        tag = self.schema + "_close"
        with self.Session() as held:
            get_locked_active_period(held)
            def close():
                with self.Session() as db:
                    db.execute(text("SELECT set_config('application_name', :tag, true)"), {"tag": tag})
                    started.set()
                    return finalize_period(self.period_id, db=db, admin="admin")
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(close)
                self.assertTrue(started.wait(timeout=2))
                deadline = monotonic() + 2
                waiting = False
                while monotonic() < deadline:
                    with self.control.connect() as connection:
                        waiting = bool(connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock'"), {"tag": tag}).scalar())
                    if waiting:
                        break
                    Event().wait(0.02)
                self.assertTrue(waiting, "Closure must wait for the in-flight shared stage gate")
                held.rollback()
                future.result(timeout=3)
        with self.Session() as db:
            self.assertEqual(db.get(Period, self.period_id).status, "CLOSED")
            self.assertEqual(db.query(Selection).one().status, "FINAL")
        self.assertEqual(self.choose(1, self.course_ids[0]), 400)
