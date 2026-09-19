import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.admin.router import reset_student_password
from app.admin.schema import StudentPasswordReset
from app.auth.router import change_password
from app.auth.dependencies import get_current_user
from app.auth.schema import PasswordChangeRequest
from app.auth.security import create_token, hash_password, verify_password
from app.database import Base
from app.models import Student, User


class PasswordManagementTest(unittest.TestCase):
    def test_long_passwords_do_not_share_a_truncated_hash(self):
        for prefix in ("a" * 72, "体" * 30):
            password_hash = hash_password(prefix + "x")
            self.assertTrue(verify_password(prefix + "x", password_hash))
            self.assertFalse(verify_password(prefix + "y", password_hash))

    def test_legacy_bcrypt_passwords_still_verify(self):
        from passlib.hash import bcrypt
        self.assertTrue(verify_password("legacy-password", bcrypt.hash("legacy-password")))

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.admin = User(
            username="admin",
            password_hash=hash_password("old-admin"),
            role="ADMIN",
        )
        self.student_user = User(
            username="2026001",
            password_hash=hash_password("old-student"),
            role="STUDENT",
        )
        self.db.add_all([self.admin, self.student_user])
        self.db.flush()

        self.student = Student(
            user_id=self.student_user.id,
            student_no="2026001",
            name="测试学生",
        )
        self.db.add(self.student)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_user_can_change_password_with_old_password(self):
        result = change_password(
            PasswordChangeRequest(
                old_password="old-admin",
                new_password="new-admin",
            ),
            username="admin",
            db=self.db,
        )

        self.db.refresh(self.admin)
        self.assertEqual(result["message"], "password changed")
        self.assertTrue(verify_password("new-admin", self.admin.password_hash))
        self.assertFalse(verify_password("old-admin", self.admin.password_hash))

    def test_wrong_old_password_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            change_password(
                PasswordChangeRequest(
                    old_password="wrong-password",
                    new_password="new-admin",
                ),
                username="admin",
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 400)

    def test_admin_can_reset_student_password(self):
        old_token = create_token(self.student_user)
        reset_student_password(
            self.student.id,
            StudentPasswordReset(new_password="reset-123456"),
            db=self.db,
            admin="admin",
        )

        student_user = self.db.query(User).filter(
            User.id == self.student.user_id
        ).one()
        self.assertTrue(verify_password("reset-123456", student_user.password_hash))
        self.assertTrue(student_user.must_change_password)
        with self.assertRaises(HTTPException) as context:
            get_current_user(token=old_token, db=self.db)
        self.assertEqual(context.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
