from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class PhonicsLesson(BaseModel):
    tag: str
    title: str
    words: List[str]


class QueryRequest(BaseModel):
    question: str
    company: str = ""
    model: str = ""

class LessonCreate(BaseModel):
    subject_id: UUID
    title: str
    description: Optional[str] = ""
    context: Optional[str] = ""
    order_index: Optional[int] = 0

class LessonOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    context: Optional[str]
    order_index: int

    class Config:
        orm_mode = True