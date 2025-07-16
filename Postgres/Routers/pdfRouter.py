
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

load_dotenv()

router = APIRouter(prefix="/pdf", tags=["PDF Ingestion"])

@router.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(...),
    title: str = Header(...),
    tag: str = Header(...),
    user_id: str = Header(None)
):
    # 🔽 Step 1: Read uploaded PDF into a temp file
    contents = await file.read()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    # 🔽 Step 2: Extract text from the PDF
    try:
        doc = fitz.open(tmp_path)
        extracted_text = "\n".join([page.get_text() for page in doc]).strip()
        doc.close()
    finally:
        os.remove(tmp_path)

    # 🔽 Step 3: Sanitize table name and create final record
    table_name = f"powellhomeschool_pdf"
    record = {"tag": tag, "title": title, "text": extracted_text}

    # 🔽 Step 4: Initialize ingestion pipeline
    ingestion = DataIngestion(
        db_config=config.DB_CONFIG,
        api_key=os.getenv("OPEN_API_KEY"),
        table_name=table_name,
        column_names=["tag", "title", "text", "lookup"],
        embedding_columns=["text"],
        embed_from="text"
    )

    # 🔽 Step 5: Chunk content and write to temp JSON
    chunks = await ingestion.dynamic_chunker(record)
    json_path = f"temp_{file.filename}.json"


    async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(chunks, ensure_ascii=False))

    # 🔽 Step 6: Embed and insert into DB
    await ingestion.process_json_file(json_path)
    os.remove(json_path)

    # 🔽 Step 7: Also insert into lessons table
    async with AsyncSessionLocal() as session:
        # 🔍 Step 1: Find subject by tag name
        subject_result = await session.execute(
            select(Subject).where(Subject.name == tag)
        )
        subject = subject_result.scalars().first()

        if not subject:
            raise HTTPException(status_code=404, detail=f"Subject '{tag}' not found")

        # 🧠 Step 2: Insert lesson tied to that subject ID
        insert_query = text("""
            INSERT INTO lessons (subject_id, title, context)
            VALUES (:subject_id, :title, :context)
        """)
        await session.execute(insert_query, {
            "subject_id": str(subject.id),
            "title": title,
            "context": extracted_text

        })
        await session.commit()

    return {
        "status": "success",
        "chunks": len(chunks),
        "table": table_name,
        "filename": file.filename
    }
