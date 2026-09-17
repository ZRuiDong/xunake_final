from sqlalchemy import CheckConstraint, Boolean, Column, Integer, String, DateTime
from app.utils.clock import app_now

from app.database import Base



class User(Base):

    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'STUDENT')",
            name="ck_users_role",
        ),
    )


    id = Column(
        Integer,
        primary_key=True
    )


    username = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )


    password_hash = Column(
        String(255),
        nullable=False
    )


    role = Column(
        String(20),
        default="STUDENT",
        nullable=False,
    )


    token_version = Column(
        Integer,
        default=0,
        nullable=False,
    )


    must_change_password = Column(
        Boolean,
        default=False,
        nullable=False,
    )


    created_time = Column(
        DateTime,
        default=app_now,
        nullable=False,
    )
