import json
import re

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from Postgres import models, schemas
from Postgres.databaseConnection import get_db
from Postgres.models import Subject, Lesson
from Postgres.schemas import LessonOut, MathLessonGenRequest
from aiManager import AiManager

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


@router.get("/by-subject/{subject_name}", response_model=List[LessonOut])
async def get_lessons_by_subject(
    subject_name: str,
    grade: Optional[int] = None,  # 👈 Add this
    db: AsyncSession = Depends(get_db)
):
    # Look up the subject first
    result = await db.execute(select(Subject).where(Subject.name == subject_name))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Build the lesson query
    stmt = select(Lesson).where(Lesson.subject_id == subject.id)
    if grade is not None:
        stmt = stmt.where(Lesson.grade == grade)

    stmt = stmt.order_by(Lesson.order_index)

    result = await db.execute(stmt)
    lessons = result.scalars().all()
    return lessons



def strip_json_code_fences(response: str) -> str:
    # Remove ```json ... ``` or ``` ... ``` fences if present
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip(), flags=re.IGNORECASE)

@router.post("/generate-math", response_model=schemas.LessonOut)
async def generate_math_flashcards(
    request: MathLessonGenRequest,
    db: AsyncSession = Depends(get_db),
):
    # 🔍 Get subject by name (not ID)
    result = await db.execute(select(models.Subject).where(models.Subject.name == request.subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject '{request.subject_id}' not found")

    # 🧠 Compose AI prompt
    prompt = f"""{request.prompt}
Return only a raw JSON array (no markdown, no triple backticks, no explanation).
Example:
[
  {{
    "question": "How many minutes are in 2.5 hours?",
    "answer": "150",
    "hint": "Multiply hours by 60 to convert to minutes."
  }},
  {{
    "question": "If 1 gallon = 4 quarts, how many gallons is 10 quarts?",
    "answer": "2.5",
    "hint": "Divide quarts by 4 to get gallons."
  }}
]
"""

    # 🤖 Use Gemini 2.0 Flash to generate
    ai = AiManager("gemini")
    raw_response = await ai.complete_json(prompt=prompt, max_tokens=600)
    print(f"ai response: {raw_response}")

    # 🔎 Validate JSON
    cleaned = strip_json_code_fences(raw_response)

    try:
        flashcards = json.loads(cleaned)
        assert isinstance(flashcards, list)
        for card in flashcards:
            assert "question" in card and "answer" in card
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid AI response format: {e}")

    # 💾 Store lesson
    lesson = models.Lesson(
        title=request.topic.strip().title(),
        subject_id=subject.id,  # ✅ use the resolved subject ID
        grade=request.grade,
        unit_no=request.unit_no,
        order_index=0,
        content=json.dumps(flashcards),
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)

    return lesson
