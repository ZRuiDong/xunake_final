from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime
)

from app.utils.clock import app_now

from app.database import Base


class Student(Base):

    __tablename__ = "students"


    id = Column(
        Integer,
        primary_key=True
    )


    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )


    student_no = Column(
        String(50),
        unique=True,
        nullable=False
    )


    name = Column(
        String(50),
        nullable=False
    )


    # Deprecated compatibility column. Admission is first-come-first-served;
    # retaining it avoids rewriting the students table during deployment.
    weight = Column(
        Float,
        default=0,
        nullable=False,
    )


    created_time = Column(
        DateTime,
        default=app_now,
        nullable=False,
    )
