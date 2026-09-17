from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from app.utils.clock import app_now

from app.database import Base


class Selection(Base):

    __tablename__ = "selections"

    __table_args__ = (
        CheckConstraint(
            "status IN ('WAITING', 'SELECTED', 'FINAL', 'REJECTED')",
            name="ck_selections_status",
        ),
        Index(
            "one_active_selection_per_student_course",
            "student_id",
            "course_id",
            unique=True,
            postgresql_where=text(
                "status IN ('WAITING', 'SELECTED', 'FINAL')"
            ),
            sqlite_where=text(
                "status IN ('WAITING', 'SELECTED', 'FINAL')"
            ),
        ),
        Index(
            "one_selection_per_student_period_course",
            "student_id",
            "period_id",
            "course_id",
            unique=True,
        ),
    )


    id = Column(
        Integer,
        primary_key=True
    )


    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
    )


    course_id = Column(
        Integer,
        ForeignKey("courses.id"),
        nullable=False,
    )


    period_id = Column(
        Integer,
        ForeignKey("periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )


    selected_time = Column(
        DateTime,
        default=app_now,
        nullable=False,
    )


    status = Column(
        String(20),
        default="WAITING",
        nullable=False,
    )

    queue_position = Column(
        Integer
    )
