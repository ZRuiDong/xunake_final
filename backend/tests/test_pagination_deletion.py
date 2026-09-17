import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.admin.router import (
    bulk_delete_courses,
    bulk_delete_students,
    get_courses_page,
    get_students_page,
)
from app.admin.schema import BulkDeleteRequest
from app.database import Base
from app.models import Course, Period, Selection, Student, User
from app.utils.clock import app_now


class PaginationDeletionTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.period = Period(
            name="测试轮次",
            start_time=app_now() - timedelta(hours=1),
            end_time=app_now() + timedelta(hours=1),
            status="ACTIVE",
        )
        self.db.add(self.period)
        self.db.flush()

        self.students = []
        for index in range(12):
            user = User(
                username=f"S{index:03d}",
                password_hash="test",
                role="STUDENT",
            )
            self.db.add(user)
            self.db.flush()
            student = Student(
                user_id=user.id,
                student_no=f"S{index:03d}",
                name=f"测试学生{index}",
                weight=index,
            )
            self.db.add(student)
            self.students.append(student)

        self.courses = [
            Course(name="绘画基础一", capacity=5, status="OPEN", period_id=self.period.id),
            Course(name="绘画基础二", capacity=5, status="OPEN", period_id=self.period.id),
            Course(name="篮球基础", capacity=5, status="OPEN", period_id=self.period.id),
        ]
        self.db.add_all(self.courses)
        self.db.flush()
        self.db.add_all([
            Selection(
                student_id=self.students[0].id,
                course_id=self.courses[0].id,
                period_id=self.period.id,
                status="SELECTED",
            ),
            Selection(
                student_id=self.students[1].id,
                course_id=self.courses[1].id,
                period_id=self.period.id,
                status="SELECTED",
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_student_pagination_returns_total_and_page_items(self):
        result = get_students_page(
            keyword="测试",
            page=2,
            page_size=5,
            db=self.db,
            admin="admin",
        )

        self.assertEqual(result["total"], 12)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(len(result["items"]), 5)

    def test_student_delete_removes_account_and_selection(self):
        student = self.students[0]
        student_id = student.id
        user_id = student.user_id
        result = bulk_delete_students(
            BulkDeleteRequest(ids=[student_id]),
            db=self.db,
            admin="admin",
        )

        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["selection_deleted_count"], 1)
        self.assertIsNone(self.db.query(Student).filter(Student.id == student_id).first())
        self.assertIsNone(self.db.query(User).filter(User.id == user_id).first())

    def test_course_search_select_all_honors_excluded_ids_and_cascades(self):
        page = get_courses_page(
            keyword="绘画",
            page=1,
            page_size=10,
            db=self.db,
            admin="admin",
        )
        self.assertEqual(page["total"], 2)

        kept_course_id = self.courses[0].id
        deleted_course_id = self.courses[1].id
        result = bulk_delete_courses(
            BulkDeleteRequest(
                select_all=True,
                keyword="绘画",
                excluded_ids=[kept_course_id],
            ),
            db=self.db,
            admin="admin",
        )

        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["selection_deleted_count"], 1)
        self.assertIsNotNone(
            self.db.query(Course).filter(Course.id == kept_course_id).first()
        )
        self.assertIsNone(
            self.db.query(Course).filter(Course.id == deleted_course_id).first()
        )


if __name__ == "__main__":
    unittest.main()
