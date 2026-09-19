import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Course, Period, Selection, Student, User
from app.utils.period import finalize_period_selections, period_status, app_now
from app.utils.selection import update_selection_status


class RoundLogicTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.period = Period(
            name="第一轮",
            start_time=app_now() - timedelta(hours=1),
            end_time=app_now() + timedelta(hours=1),
            status="ACTIVE",
        )
        self.db.add(self.period)
        self.db.flush()

        self.course = Course(
            name="测试课程",
            capacity=1,
            status="OPEN",
            period_id=self.period.id,
        )
        self.db.add(self.course)

        for index in range(1, 3):
            user = User(
                username=f"student-{index}",
                password_hash="not-used",
                role="STUDENT",
            )
            self.db.add(user)
            self.db.flush()
            self.db.add(Student(
                user_id=user.id,
                student_no=f"S{index}",
                name=f"学生{index}",
            ))

        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_period_status_follows_time_window(self):
        now = app_now()
        self.assertEqual(
            period_status(now + timedelta(minutes=1), now + timedelta(minutes=2), now),
            "WAITING",
        )
        self.assertEqual(
            period_status(now - timedelta(minutes=1), now + timedelta(minutes=1), now),
            "ACTIVE",
        )
        self.assertEqual(
            period_status(now - timedelta(minutes=2), now - timedelta(minutes=1), now),
            "CLOSED",
        )

    def test_first_application_gets_capacity_and_later_one_waits(self):
        students = self.db.query(Student).order_by(Student.id).all()
        for index, student in enumerate(students):
            self.db.add(Selection(
                student_id=student.id,
                course_id=self.course.id,
                period_id=self.period.id,
                selected_time=app_now() + timedelta(seconds=index),
                status="WAITING",
            ))
        self.db.flush()

        update_selection_status(self.course.id, self.db)

        first_selection = self.db.query(Selection).filter(
            Selection.student_id == students[0].id
        ).one()
        later_selection = self.db.query(Selection).filter(
            Selection.student_id == students[1].id
        ).one()
        self.assertEqual(first_selection.status, "SELECTED")
        self.assertEqual(later_selection.status, "WAITING")

    def test_final_students_can_exceed_capacity(self):
        students = self.db.query(Student).all()
        for student in students:
            self.db.add(Selection(
                student_id=student.id,
                course_id=self.course.id,
                period_id=self.period.id,
                selected_time=app_now(),
                status="FINAL",
            ))
        self.db.flush()

        update_selection_status(self.course.id, self.db)

        statuses = [item.status for item in self.db.query(Selection).all()]
        self.assertEqual(statuses, ["FINAL", "FINAL"])

    def test_finalizing_marks_waitlisted_students_as_rejected(self):
        students = self.db.query(Student).order_by(Student.id).all()
        self.db.add_all([
            Selection(
                student_id=students[0].id,
                course_id=self.course.id,
                period_id=self.period.id,
                status="SELECTED",
            ),
            Selection(
                student_id=students[1].id,
                course_id=self.course.id,
                period_id=self.period.id,
                status="WAITING",
            ),
        ])
        self.db.flush()

        finalized_count = finalize_period_selections(self.period.id, self.db)

        statuses = {
            item.student_id: item.status
            for item in self.db.query(Selection).all()
        }
        self.assertEqual(finalized_count, 1)
        self.assertEqual(statuses[students[0].id], "FINAL")
        self.assertEqual(statuses[students[1].id], "REJECTED")


if __name__ == "__main__":
    unittest.main()
