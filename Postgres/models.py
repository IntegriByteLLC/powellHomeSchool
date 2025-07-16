import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text
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
    grade = Column(String)
    context = Column(Text)
    order_index = Column(Integer, default=0)
    subject = relationship("Subject", back_populates="lessons")
