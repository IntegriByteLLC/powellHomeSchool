import uuid

from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from powpow.ingestion import DataIngestion
import fitz  # PyMuPDF
import os, time, re, json
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv
import aiofiles
from sqlalchemy import text
from sqlalchemy.future import select

from Postgres.config import config
from Postgres.databaseConnection import AsyncSessionLocal
from Postgres.models import Subject
from Postgres.schemas import OCRTextRequest

load_dotenv()

router = APIRouter(prefix="/pdf", tags=["PDF Ingestion"])

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import traceback

@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(...),
    title: str = Header(...),
    tag: str = Header(...),
    unit: str = Header(...),
    grade: str = Header(...)

):
    try:
        contents = await file.read()
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            doc = fitz.open(tmp_path)
            extracted_text = "\n".join([page.get_text() for page in doc]).strip()
            doc.close()
        finally:
            os.remove(tmp_path)

        table_name = f"powellhomeschool_pdf"
        record = {"tag": tag, "title": title, "text": extracted_text}

        ingestion = DataIngestion(
            db_config=config.DB_CONFIG,
            api_key=os.getenv("OPEN_API_KEY"),
            table_name=table_name,
            column_names=["tag", "title", "text", "lookup"],
            embedding_columns=["text"],
            embed_from="text"
        )

        chunks = await ingestion.dynamic_chunker(record)
        json_path = f"temp_{file.filename}.json"

        async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(chunks, ensure_ascii=False))

        await ingestion.process_json_file(json_path)
        os.remove(json_path)

        async with AsyncSessionLocal() as session:
            subject_result = await session.execute(
                select(Subject).where(Subject.name == tag)
            )
            subject = subject_result.scalars().first()

            if not subject:
                raise HTTPException(status_code=404, detail=f"Subject '{tag}' not found")

            insert_query = text("""
                INSERT INTO lessons (subject_id, title, content, unit_no, grade)
                VALUES (:subject_id, :title, :content, :unit_no, :grade)
            """)
            await session.execute(insert_query, {
                "subject_id": str(subject.id),
                "title": title,
                "content": extracted_text,
                "unit_no": int(unit),
                "grade": int(grade)
            })

            await session.commit()

        return {
            "status": "success",
            "chunks": len(chunks),
            "table": table_name,
            "filename": file.filename
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({"error": str(e)})
        )



@router.post("/ocr-text")
async def ingest_ocr_text(
    payload: OCRTextRequest,
    title: str = Header(...),
    tag: str = Header(...),
    user_id: str = Header(None),
):
    # ✅ Step 1: Prepare record
    extracted_text = payload.text.strip()
    table_name = f"powellhomeschool_pdf"
    record = {"tag": tag, "title": title, "text": extracted_text}

    # ✅ Step 2: Ingest and chunk
    ingestion = DataIngestion(
        db_config=config.DB_CONFIG,
        api_key=os.getenv("OPEN_API_KEY"),
        table_name=table_name,
        column_names=["tag", "title", "text", "lookup"],
        embedding_columns=["text"],
        embed_from="text"
    )

    chunks = await ingestion.dynamic_chunker(record)
    json_path = f"ocr_temp_{uuid.uuid4().hex}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    await ingestion.process_json_file(json_path)
    os.remove(json_path)

    # ✅ Step 3: Save into lessons table
    async with AsyncSessionLocal() as session:
        subject_result = await session.execute(
            select(Subject).where(Subject.name == tag)
        )
        subject = subject_result.scalars().first()

        if not subject:
            raise HTTPException(status_code=404, detail=f"Subject '{tag}' not found")

        insert_query = text("""
            INSERT INTO lessons (subject_id, title, content)
            VALUES (:subject_id, :title, :content)
        """)
        await session.execute(insert_query, {
            "subject_id": str(subject.id),
            "title": title,
            "content": extracted_text
        })

        await session.commit()

    return {
        "status": "success",
        "chunks": len(chunks),
        "source": "ocr",
        "table": table_name
    }