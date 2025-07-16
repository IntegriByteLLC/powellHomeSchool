from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from Postgres.schemas import PhonicsLesson

router = APIRouter(prefix="/phonics", tags=["Phonics Lessons"])



@router.post("/ingest")
async def ingest_lesson(lesson: PhonicsLesson):
    # Placeholder: Insert to DB, generate audio later
    return {"status": "received", "tag": lesson.tag, "word_count": len(lesson.words)}
