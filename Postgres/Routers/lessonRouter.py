from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from Postgres import models, schemas
from Postgres.databaseConnection import get_db
from Postgres.models import Subject, Lesson
from Postgres.schemas import LessonOut

router = APIRouter(prefix="/lesson", tags=["Lesson"])

@router.post("", response_model=schemas.LessonOut)
async def create_lesson(data: schemas.LessonCreate, db: AsyncSession = Depends(get_db)):
    subject = await db.get(models.Subject, data.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    lesson = models.Lesson(**data.dict())
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson

@router.get("/{subject_id}", response_model=List[schemas.LessonOut])
async def get_lessons_by_subject(subject_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Lesson).where(models.Lesson.subject_id == subject_id).order_by(models.Lesson.order_index)
    )
    return result.scalars().all()


@router.get("/by-subject/{subject_name}", response_model=list[LessonOut])
async def get_lessons_by_subject(subject_name: str, db: AsyncSession = Depends(get_db)):
    # Look up the subject first
    result = await db.execute(select(Subject).where(Subject.name == subject_name))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Now look up lessons for that subject
    result = await db.execute(
        select(Lesson).where(Lesson.subject_id == subject.id).order_by(Lesson.order_index)
    )
    lessons = result.scalars().all()
    return lessons