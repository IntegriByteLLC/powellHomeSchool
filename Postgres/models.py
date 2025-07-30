import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from Postgres.databaseConnection import Base


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    lessons = relationship("Lesson", back_populates="subject", cascade="all, delete")

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    grade = Column(Integer)
    unit_no = Column(Integer)  # ✅ Renamed and changed to Integer
    content = Column(Text)
    order_index = Column(Integer, default=0)

    subject = relationship("Subject", back_populates="lessons")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String)
    grade = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)