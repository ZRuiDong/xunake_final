from math import isfinite

from pydantic import BaseModel, Field, field_validator, model_validator


class StudentCreate(BaseModel):

    student_no: str = Field(min_length=1, max_length=50)

    name: str = Field(min_length=1, max_length=50)

    weight:float

    password: str = Field(min_length=6, max_length=128)

    @field_validator("student_no", "name")
    @classmethod
    def strip_required_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, value: float):
        if not isfinite(value):
            raise ValueError("weight must be finite")
        return value


class StudentUpdate(BaseModel):

    student_no: str = Field(min_length=1, max_length=50)

    name: str = Field(min_length=1, max_length=50)

    weight: float

    @field_validator("student_no", "name")
    @classmethod
    def strip_required_text(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, value: float):
        if not isfinite(value):
            raise ValueError("weight must be finite")
        return value


class StudentPasswordReset(BaseModel):

    new_password: str = Field(min_length=6, max_length=128)


class BulkDeleteRequest(BaseModel):

    ids: list[int] = Field(default_factory=list)

    select_all: bool = False

    keyword: str | None = None

    excluded_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_selection(self):
        if not self.select_all and not self.ids:
            raise ValueError("no records selected")
        return self
