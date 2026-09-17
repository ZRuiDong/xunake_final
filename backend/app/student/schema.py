from pydantic import BaseModel


class CourseInfo(BaseModel):

    id:int

    name:str

    capacity:int

    selected_count:int

    class Config:

        from_attributes=True