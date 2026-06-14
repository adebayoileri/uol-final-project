from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CourseRequest(BaseModel):
    goal: str = Field(..., min_length=10, max_length=1000)
    duration: Literal["short_term", "long_term"]
    category: str = Field(..., min_length=2, max_length=100)


class ObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    description: str


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    title: str
    description: str
    duration_minutes: int
    objectives: list[ObjectiveResponse]


class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    title: str
    description: str
    lessons: list[LessonResponse]


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    duration: str
    category: str
    title: str
    description: str
    created_at: datetime
    modules: list[ModuleResponse]
