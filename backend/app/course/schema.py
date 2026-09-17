from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CourseCreate(BaseModel):

    name:str = Field(min_length=1, max_length=100)

    description:str | None = Field(default=None, max_length=500)

    instructor:str | None = Field(default=None, max_length=100)

    location:str | None = Field(default=None, max_length=200)

    schedule:str | None = Field(default=None, max_length=200)

    capacity:int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("course name cannot be blank")
        return value

    @field_validator("description", "instructor", "location", "schedule")
    @classmethod
    def normalize_optional_text(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None


class CourseStatusUpdate(BaseModel):

    status: Literal["OPEN", "CLOSED"]



class CourseResponse(BaseModel):

    id:int

    name:str

    description:str | None

    instructor:str | None = None

    location:str | None = None

    schedule:str | None = None

    capacity:int

    status:str

    period_id:int | None = None


    class Config:

        from_attributes=True
