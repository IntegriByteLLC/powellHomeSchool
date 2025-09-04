from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class PhonicsLesson(BaseModel):
    tag: str
    title: str
    words: List[str]


class QueryRequest(BaseModel):
    question: str
    provider: Optional[str] = None
    model: Optional[str] = None

class LessonCreate(BaseModel):
    subject_id: UUID
    title: str
    grade: Optional[int] = None
    unit_no: Optional[int] = None  # ✅ Renamed and type changed
    content: Optional[str] = ""
    order_index: Optional[int] = 0

class LessonOut(BaseModel):
    id: UUID
    title: str
    grade: Optional[int] = None
    unit_no: Optional[int] = None  # ✅ Renamed and type changed
    content: Optional[str]
    order_index: int

    class Config:
        orm_mode = True


class MathLessonGenRequest(BaseModel):
    topic: str
    subject_id: str
    prompt: str
    grade: Optional[int] = None
    unit_no: Optional[int] = None




class OCRTextRequest(BaseModel):
    text: str


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: Optional[str] = "user"
    grade: str
    is_active: Optional[bool] = True

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[str]
    grade: Optional[str]
    is_active: Optional[bool]

class UserOut(UserBase):
    id: UUID
    class Config:
        orm_mode = True
