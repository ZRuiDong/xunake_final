from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String

from app.database import Base


class Course(Base):

    __tablename__ = "courses"

    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_courses_capacity_positive"),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_courses_status",
        ),
    )


    id = Column(
        Integer,
        primary_key=True
    )


    name = Column(
        String(100),
        unique=True,
        nullable=False
    )


    description = Column(
        String(500)
    )


    instructor = Column(
        String(100)
    )


    location = Column(
        String(200)
    )


    schedule = Column(
        String(200)
    )


    capacity = Column(
        Integer,
        nullable=False
    )


    status = Column(
        String(20),
        default="OPEN",
        nullable=False,
    )


    period_id = Column(
        Integer,
        ForeignKey("periods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
