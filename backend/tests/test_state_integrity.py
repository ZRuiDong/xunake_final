import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.admin.period_schema import PeriodCourseAdd, PeriodUpdate
from app.admin.router import (
    add_period_courses,
    admin_add_student,
    admin_remove_student,
    bulk_delete_students,
    get_available_students,
    remove_period_course,
    update_period,
    update_student,
)
from app.admin.schema import BulkDeleteRequest, StudentUpdate
from app.course.router import update_course
from app.course.schema import CourseCreate
from app.database import Base
from app.models import Course, Period, Selection, Student, User
from app.student.router import cancel_course, select_course, get_courses
from app.utils.period import get_locked_active_period, app_now


class StateIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_period(self, status="CLOSED", capacity=1):
        now = app_now()
        if status == "WAITING":
            start_time = now + timedelta(hours=1)
            end_time = now + timedelta(hours=2)
        elif status == "ACTIVE":
            start_time = now - timedelta(hours=1)
            end_time = now + timedelta(hours=1)
        else:
            start_time = now - timedelta(hours=2)
            end_time = now - timedelta(hours=1)
        period = Period(
            name=f"{status}阶段",
            start_time=start_time,
            end_time=end_time,
            status=status,
        )
        self.db.add(period)
        self.db.flush()
        course = Course(
            name=f"{status}课程",
            capacity=capacity,
            status="OPEN",
            period_id=period.id,
        )
        self.db.add(course)
        self.db.flush()
        return period, course

    def create_student(self, suffix, _unused_priority=None):
        user = User(
            username=f"S{suffix}",
            password_hash="test",
            role="STUDENT",
        )
        self.db.add(user)
        self.db.flush()
        student = Student(
            user_id=user.id,
            student_no=f"S{suffix}",
            name=f"学生{suffix}",
        )
        self.db.add(student)
        self.db.flush()
        return user, student

    def test_closed_period_removal_does_not_promote_rejected_student(self):
        period, course = self.create_period("CLOSED", capacity=1)
        _, final_student = self.create_student("001", 10)
        _, waiting_student = self.create_student("002", 5)
        self.db.add_all([
            Selection(
                student_id=final_student.id,
                course_id=course.id,
                period_id=period.id,
                status="FINAL",
            ),
            Selection(
                student_id=waiting_student.id,
                course_id=course.id,
                period_id=period.id,
                status="REJECTED",
            ),
        ])
        self.db.commit()

        admin_remove_student(
            course.id,
            final_student.id,
            db=self.db,
            admin="admin",
        )

        remaining = self.db.query(Selection).one()
        self.assertEqual(remaining.student_id, waiting_student.id)
        self.assertEqual(remaining.status, "REJECTED")

    def test_closed_period_admin_can_admit_a_rejected_student(self):
        period, course = self.create_period("CLOSED", capacity=1)
        _, final_student = self.create_student("003", 10)
        _, rejected_student = self.create_student("004", 5)
        self.db.add_all([
            Selection(
                student_id=final_student.id,
                course_id=course.id,
                period_id=period.id,
                status="FINAL",
            ),
            Selection(
                student_id=rejected_student.id,
                course_id=course.id,
                period_id=period.id,
                status="REJECTED",
            ),
        ])
        self.db.commit()

        result = admin_add_student(
            course.id,
            rejected_student.id,
            allow_over_capacity=True,
            db=self.db,
            admin="admin",
        )

        statuses = [item.status for item in self.db.query(Selection).all()]
        self.assertEqual(statuses, ["FINAL", "FINAL"])
        self.assertTrue(result["over_capacity"])

    def test_admin_can_add_two_courses_but_not_a_third(self):
        period, first_course = self.create_period("ACTIVE", capacity=5)
        second_course = Course(
            name="管理员第二门课程",
            capacity=5,
            status="OPEN",
            period_id=period.id,
        )
        third_course = Course(
            name="管理员第三门课程",
            capacity=5,
            status="OPEN",
            period_id=period.id,
        )
        self.db.add_all([second_course, third_course])
        _, student = self.create_student("004A", 5)
        self.db.commit()

        admin_add_student(first_course.id, student.id, db=self.db, admin="admin")
        admin_add_student(second_course.id, student.id, db=self.db, admin="admin")
        with self.assertRaises(HTTPException) as context:
            admin_add_student(third_course.id, student.id, db=self.db, admin="admin")

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            self.db.query(Selection).filter(Selection.student_id == student.id).count(),
            2,
        )

    def test_admin_student_search_only_hides_students_at_two_course_limit(self):
        period, first_course = self.create_period("ACTIVE", capacity=5)
        second_course = Course(
            name="可用学生筛选课程",
            capacity=5,
            status="OPEN",
            period_id=period.id,
        )
        self.db.add(second_course)
        _, one_course_student = self.create_student("004B", 5)
        _, two_course_student = self.create_student("004C", 5)
        self.db.flush()
        self.db.add_all([
            Selection(
                student_id=one_course_student.id,
                course_id=first_course.id,
                period_id=period.id,
                status="SELECTED",
            ),
            Selection(
                student_id=two_course_student.id,
                course_id=first_course.id,
                period_id=period.id,
                status="SELECTED",
            ),
            Selection(
                student_id=two_course_student.id,
                course_id=second_course.id,
                period_id=period.id,
                status="WAITING",
            ),
        ])
        self.db.commit()

        available = get_available_students(
            keyword="",
            limit=50,
            db=self.db,
            admin="admin",
        )
        available_ids = {item["id"] for item in available}

        self.assertIn(one_course_student.id, available_ids)
        self.assertNotIn(two_course_student.id, available_ids)

    def test_deleting_student_does_not_change_closed_roster(self):
        period, course = self.create_period("CLOSED", capacity=1)
        _, final_student = self.create_student("005", 10)
        _, waiting_student = self.create_student("006", 5)
        self.db.add_all([
            Selection(
                student_id=final_student.id,
                course_id=course.id,
                period_id=period.id,
                status="FINAL",
            ),
            Selection(
                student_id=waiting_student.id,
                course_id=course.id,
                period_id=period.id,
                status="REJECTED",
            ),
        ])
        self.db.commit()

        bulk_delete_students(
            BulkDeleteRequest(ids=[final_student.id]),
            db=self.db,
            admin="admin",
        )

        remaining = self.db.query(Selection).one()
        self.assertEqual(remaining.student_id, waiting_student.id)
        self.assertEqual(remaining.status, "REJECTED")

    def test_reopening_closed_period_keeps_finals_and_reranks_others(self):
        period, course = self.create_period("CLOSED", capacity=1)
        _, final_student = self.create_student("011", 1)
        _, waiting_student = self.create_student("012", 100)
        self.db.add_all([
            Selection(
                student_id=final_student.id,
                course_id=course.id,
                period_id=period.id,
                status="FINAL",
            ),
            Selection(
                student_id=waiting_student.id,
                course_id=course.id,
                period_id=period.id,
                status="REJECTED",
            ),
        ])
        self.db.commit()

        now = app_now()
        result = update_period(
            period.id,
            PeriodUpdate(
                name=period.name,
                start_time=now - timedelta(minutes=1),
                end_time=now + timedelta(hours=1),
            ),
            db=self.db,
            admin="admin",
        )

        statuses = {
            item.student_id: item.status
            for item in self.db.query(Selection).all()
        }
        self.assertTrue(result["reopened"])
        self.assertEqual(statuses[final_student.id], "FINAL")
        self.assertEqual(statuses[waiting_student.id], "WAITING")

    def test_waiting_period_course_can_be_removed(self):
        period, course = self.create_period("WAITING")
        self.db.commit()

        remove_period_course(period.id, course.id, db=self.db, admin="admin")

        self.db.refresh(course)
        self.assertIsNone(course.period_id)

    def test_student_update_changes_account_without_changing_selection_order(self):
        period, course = self.create_period("ACTIVE", capacity=1)
        user_one, student_one = self.create_student("021", 1)
        _, student_two = self.create_student("022", 10)
        self.db.add_all([
            Selection(
                student_id=student_one.id,
                course_id=course.id,
                period_id=period.id,
                status="WAITING",
            ),
            Selection(
                student_id=student_two.id,
                course_id=course.id,
                period_id=period.id,
                status="SELECTED",
            ),
        ])
        self.db.commit()

        update_student(
            student_one.id,
            StudentUpdate(student_no="S099", name="新姓名"),
            db=self.db,
            admin="admin",
        )

        self.db.refresh(student_one)
        self.db.refresh(user_one)
        selection = self.db.query(Selection).filter(
            Selection.student_id == student_one.id
        ).one()
        self.assertEqual(student_one.student_no, "S099")
        self.assertEqual(user_one.username, "S099")
        self.assertEqual(selection.status, "WAITING")

    def test_student_can_select_two_courses_but_not_a_third(self):
        period, course = self.create_period("ACTIVE", capacity=2)
        second_course = Course(
            name="第二门课程",
            capacity=2,
            status="OPEN",
            period_id=period.id,
        )
        third_course = Course(
            name="第三门课程",
            capacity=2,
            status="OPEN",
            period_id=period.id,
        )
        self.db.add_all([second_course, third_course])
        user, student = self.create_student("031", 1)
        self.db.commit()

        select_course(course.id, db=self.db, username=user.username)
        select_course(second_course.id, db=self.db, username=user.username)
        with self.assertRaises(HTTPException) as context:
            select_course(third_course.id, db=self.db, username=user.username)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "student can select at most two courses",
        )
        self.assertEqual(
            self.db.query(Selection).filter(Selection.student_id == student.id).count(),
            2,
        )

    def test_rejected_student_can_select_in_a_later_period(self):
        old_period, old_course = self.create_period("CLOSED")
        user, student = self.create_student("041", 8)
        self.db.add(Selection(
            student_id=student.id,
            course_id=old_course.id,
            period_id=old_period.id,
            status="REJECTED",
        ))
        new_period, new_course = self.create_period("ACTIVE")
        new_period.name = "后续阶段"
        new_course.name = "后续课程"
        self.db.commit()

        result = select_course(
            new_course.id,
            db=self.db,
            username=user.username,
        )

        selections = self.db.query(Selection).filter(
            Selection.student_id == student.id
        ).order_by(Selection.period_id).all()
        self.assertEqual(result["status"], "SELECTED")
        self.assertEqual([item.status for item in selections], ["REJECTED", "SELECTED"])

    def test_student_can_cancel_and_select_another_course(self):
        period, first_course = self.create_period("ACTIVE", capacity=1)
        second_course = Course(
            name="可重选课程",
            capacity=1,
            status="OPEN",
            period_id=period.id,
        )
        self.db.add(second_course)
        user, student = self.create_student("051", 5)
        self.db.commit()

        select_course(first_course.id, db=self.db, username=user.username)
        cancel_course(first_course.id, db=self.db, username=user.username)
        result = select_course(second_course.id, db=self.db, username=user.username)

        selection = self.db.query(Selection).filter(
            Selection.student_id == student.id
        ).one()
        self.assertEqual(result["status"], "SELECTED")
        self.assertEqual(selection.course_id, second_course.id)

    def test_cancel_promotes_the_earliest_waiting_student(self):
        _, course = self.create_period("ACTIVE", capacity=1)
        users_and_students = [
            self.create_student(f"queue{index}", index)
            for index in range(3)
        ]
        self.db.commit()

        for user, _ in users_and_students:
            select_course(course.id, db=self.db, username=user.username)

        cancel_course(
            course.id,
            db=self.db,
            username=users_and_students[0][0].username,
        )

        queue = self.db.query(Selection).filter(
            Selection.course_id == course.id,
        ).order_by(Selection.selected_time, Selection.id).all()
        self.assertEqual(
            [item.student_id for item in queue],
            [users_and_students[1][1].id, users_and_students[2][1].id],
        )
        self.assertEqual(
            [item.status for item in queue],
            ["SELECTED", "WAITING"],
        )

    def test_active_period_accepts_new_courses(self):
        period, _ = self.create_period("ACTIVE")
        course = Course(name="进行中新增课程", capacity=10, status="OPEN")
        self.db.add(course)
        self.db.commit()

        result = add_period_courses(
            period.id,
            PeriodCourseAdd(course_ids=[course.id]),
            db=self.db,
            admin="admin",
        )

        self.db.refresh(course)
        self.assertEqual(result["count"], 1)
        self.assertEqual(course.period_id, period.id)

    def test_active_capacity_change_reranks_non_final_students(self):
        period, course = self.create_period("ACTIVE", capacity=2)
        _, first = self.create_student("061", 10)
        _, later = self.create_student("062", 1)
        self.db.add_all([
            Selection(
                student_id=first.id,
                course_id=course.id,
                period_id=period.id,
                status="SELECTED",
            ),
            Selection(
                student_id=later.id,
                course_id=course.id,
                period_id=period.id,
                status="SELECTED",
            ),
        ])
        self.db.commit()

        update_course(
            course.id,
            CourseCreate(name=course.name, capacity=1),
            db=self.db,
            admin="admin",
        )

        statuses = {
            item.student_id: item.status
            for item in self.db.query(Selection).all()
        }
        self.assertEqual(statuses[first.id], "SELECTED")
        self.assertEqual(statuses[later.id], "WAITING")

    def test_expired_active_period_is_closed_before_selection_write(self):
        period, _ = self.create_period("ACTIVE")
        period.end_time = app_now() - timedelta(seconds=1)
        self.db.commit()

        locked = get_locked_active_period(self.db)

        self.assertIsNone(locked)
        self.db.refresh(period)
        self.assertEqual(period.status, "CLOSED")

    def test_reselect_only_revives_the_target_courses_history(self):
        period, first = self.create_period("ACTIVE")
        second = Course(name="second history", capacity=2, period_id=period.id)
        self.db.add(second)
        user, student = self.create_student("history", 2)
        self.db.flush()
        for course in (first, second):
            self.db.add(Selection(student_id=student.id, course_id=course.id,
                                  period_id=period.id, status="REJECTED"))
        self.db.commit()
        select_course(second.id, db=self.db, username=user.username)
        records = {s.course_id: s.status for s in self.db.query(Selection).all()}
        self.assertEqual(records, {first.id: "REJECTED", second.id: "SELECTED"})

    def test_expired_admin_removal_never_promotes_waitlist(self):
        period, course = self.create_period("ACTIVE")
        _, winner = self.create_student("winner", 10)
        _, waiting = self.create_student("waiting", 1)
        self.db.add_all([
            Selection(student_id=winner.id, course_id=course.id,
                      period_id=period.id, status="SELECTED"),
            Selection(student_id=waiting.id, course_id=course.id,
                      period_id=period.id, status="WAITING"),
        ])
        period.end_time = app_now() - timedelta(seconds=1)
        self.db.commit()
        admin_remove_student(course.id, winner.id, db=self.db, admin="admin")
        self.assertEqual(self.db.query(Selection).one().status, "REJECTED")
        self.assertEqual(self.db.get(Period, period.id).status, "CLOSED")

    def test_over_capacity_closed_course_allows_metadata_changes(self):
        period, course = self.create_period("CLOSED", capacity=1)
        for suffix in ("over1", "over2"):
            _, student = self.create_student(suffix, 1)
            self.db.add(Selection(student_id=student.id, course_id=course.id,
                                  period_id=period.id, status="FINAL"))
        self.db.commit()
        update_course(course.id, CourseCreate(name=course.name, capacity=1,
                      description="new description"), db=self.db, admin="admin")
        self.assertEqual(self.db.get(Course, course.id).description, "new description")

    def test_duplicate_select_and_cancel_are_idempotent(self):
        _, course = self.create_period("ACTIVE")
        user, _ = self.create_student("retry", 1)
        self.db.commit()
        select_course(course.id, db=self.db, username=user.username)
        select_course(course.id, db=self.db, username=user.username)
        self.assertEqual(self.db.query(Selection).count(), 1)
        cancel_course(course.id, db=self.db, username=user.username)
        cancel_course(course.id, db=self.db, username=user.username)
        self.assertEqual(self.db.query(Selection).count(), 0)

    def test_catalog_query_count_does_not_grow_with_course_count(self):
        period, _ = self.create_period("ACTIVE")
        self.create_student("catalog", 1)
        self.db.add_all([Course(name=f"catalog {i}", capacity=10,
                               period_id=period.id) for i in range(30)])
        self.db.commit()
        statements = []
        def count_statement(*args):
            statements.append(args[2])
        event.listen(self.engine, "before_cursor_execute", count_statement)
        try:
            result = get_courses(db=self.db, username="Scatalog")
        finally:
            event.remove(self.engine, "before_cursor_execute", count_statement)
        self.assertEqual(len(result), 31)
        self.assertLessEqual(len(statements), 8)


if __name__ == "__main__":
    unittest.main()
