from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from app.utils.clock import APP_TIMEZONE


def normalize_datetime(value: datetime):
    if value.tzinfo is None:
        return value
    return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)


class PeriodCreate(BaseModel):

    name: str = Field(min_length=1, max_length=100)

    start_time: datetime

    end_time: datetime

    course_ids: list[int] = Field(min_length=1)

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_time(cls, value: datetime):
        return normalize_datetime(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("period name cannot be blank")
        return value


class PeriodUpdate(BaseModel):

    name: str = Field(min_length=1, max_length=100)

    start_time: datetime

    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_time(cls, value: datetime):
        return normalize_datetime(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("period name cannot be blank")
        return value


class PeriodCourseAdd(BaseModel):

    course_ids: list[int] = Field(min_length=1)
