import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import AuditLog, Student, User
from app.admin.schema import BulkDeleteRequest
from app.admin.router import bulk_delete_students


class DeletionAuditTest(unittest.TestCase):
    def test_deletion_keeps_a_snapshot_without_passwords(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            user = User(username="audit", password_hash="not-to-be-exported", role="STUDENT")
            db.add(user)
            db.flush()
            student = Student(user_id=user.id, student_no="audit", name="audit student", weight=2)
            db.add(student)
            db.commit()
            bulk_delete_students(BulkDeleteRequest(ids=[student.id]), db=db, admin="admin")
            audit = db.query(AuditLog).one()
            self.assertEqual(audit.actor, "admin")
            self.assertEqual(audit.snapshot["entities"][0]["student_no"], "audit")
            self.assertNotIn("password_hash", str(audit.snapshot))
            self.assertEqual(db.query(Student).count(), 0)
        engine.dispose()
