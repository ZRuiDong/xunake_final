from sqlalchemy import CheckConstraint, Column, Integer, String, DateTime

from app.database import Base


class Period(Base):

    __tablename__ = "periods"

    __table_args__ = (
        CheckConstraint(
            "status IN ('WAITING', 'ACTIVE', 'CLOSED')",
            name="ck_periods_status",
        ),
        CheckConstraint("end_time > start_time", name="ck_periods_time_range"),
    )


    id = Column(
        Integer,
        primary_key=True
    )


    name = Column(
        String(100),
        nullable=False,
    )


    start_time = Column(
        DateTime,
        nullable=False,
    )


    end_time = Column(
        DateTime,
        nullable=False,
    )


    status = Column(
        String(20),
        default="WAITING",
        nullable=False,
    )

    finalized_time = Column(
        DateTime,
        nullable=True
    )
