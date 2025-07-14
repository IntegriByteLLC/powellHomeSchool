# main.py
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from asyncio import gather
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import List
import jwt
from PyPDF2 import PdfReader
from fastapi.logger import logger
from fastapi.responses import JSONResponse
import asyncpg
from fastapi import FastAPI, HTTPException, Depends, Request, Header, status, UploadFile, File
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
import aiofiles
from AutomateScraper.automateScrape import scrape_urls, dynamic_chunker
import fitz
from aiManager import AiManager
from Mail import models, database, schemas
from powpow.logger import enable_debug
from powpow.ingestion import DataIngestion
from powpow.database import Database


load_dotenv()


OPENAI_API_KEY = os.getenv("OPEN_API_KEY")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

DB_CONFIG = {
    "user": os.getenv("DB_USER", "powellhomeschool"),
    "password": os.getenv("DB_PASS", "@powe!!homeschool2025"),
    "database": os.getenv("DB_NAME", "powellhomeschool"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "7894")),
}


MASTER_KEY = os.getenv("MASTER_API_KEY", "")
db_tables: dict[str, Database] = {}


# Initialize FastAPI and GPTManager
app = FastAPI()
db_pool = None


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.on_event("startup")
async def startup():
    global db_pool, db_tables
    db_pool = await asyncpg.create_pool(**DB_CONFIG)

    TABLE_SUFFIXES = ["", "_pdf", "_urls"]
    TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tag TEXT,
            title TEXT,
            text TEXT,
            lookup VECTOR(1536)
        
        )
    """

    async with db_pool.acquire() as conn:
        for suffix in TABLE_SUFFIXES:
            table = f"powellhomeschool{suffix}"
            db_tables[table] = Database(DB_CONFIG, api_key=OPENAI_API_KEY, table_name=table)

            # Auto-create the table if it doesn't exist
            create_sql = TABLE_SCHEMA.format(table_name=table)
            try:
                await conn.execute(create_sql)
                print(f"✅ Ensured table exists: {table}")
            except Exception as e:
                print(f"❌ Failed to create table '{table}': {e}")



@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()


def get_current_token() -> str:

    current_hour = str(int(time.time()) // 3600)
    return hmac.new(MASTER_KEY.encode(), current_hour.encode(), hashlib.sha256).hexdigest()

def verify_token(request: Request):
    token = request.headers.get("x-chat-token")
    if not token:
        raise HTTPException(status_code=403, detail="Missing token")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload  # e.g. {'sub': 'user_id', 'email': '...', 'company_id': '...'}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")


PERSONA_MAP = {
    "powellhomeschool": (
        "You are an educational assistant for Powell HomeSchool. "
        "Use only the provided learning materials to answer questions. "
        "Do not guess or respond outside the scope of Powell HomeSchool content. "
        "If no relevant data is found, say: "
        "\"I can only respond based on Powell HomeSchool’s materials.\""
    )

}

MODEL_TOKEN_LIMITS = {
    "gpt-4-0613": 8192,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-instruct": 4096,
    "gpt-3.5-turbo-instruct-0914": 4096,
    "gpt-3.5-turbo-1106": 16000,
    "gpt-3.5-turbo-0125": 16000,

    # default for new models
    "default": 128000
}

def estimate_tokens(text: str) -> int:
    # Approximate: 1 token ≈ 4 characters in English
    return len(text) // 4

def trim_context_to_token_limit(text: str, token_limit: int) -> str:
    approx_char_limit = token_limit * 4
    return text[:approx_char_limit]

class QueryRequest(BaseModel):
    question: str
    company: str = ""
    model: str = ""


@app.post("/ask")
async def ask_question(req: QueryRequest, request: Request):
    provider = req.company.lower()
    model = req.model
    ai = AiManager(provider=provider)
    start_time = time.monotonic()

    table = "powellhomeschool_urls"
    db = db_tables.get(table)

    combined_context = ""

    if db:
        try:
            results = await db.search_query(req.question, column_names=["title", "text"], top_n=10)
            if results:
                combined_context = "\n\n".join(
                    f"{r.get('title', '')}\n{r.get('text', '')}" for r in results if 'text' in r
                )
        except Exception as e:
            logger.warning(f"Search failed for table '{table}': {e}")
    else:
        logger.warning(f"No DB handler found for table '{table}'")

    # Token trimming
    token_limit = MODEL_TOKEN_LIMITS.get(model, MODEL_TOKEN_LIMITS["default"])
    max_context_tokens = token_limit - 1000
    if estimate_tokens(combined_context) > max_context_tokens:
        combined_context = trim_context_to_token_limit(combined_context, max_context_tokens)
    print(f"Combinded text: {combined_context}")
    end_time = time.monotonic()
    print(f"⏱️ DB search for /ask took {round((end_time - start_time) * 1000)} ms")

    response = await ai.ask(
        query=req.question,
        context_for_prompt=combined_context,
        persona=PERSONA_MAP.get("powellhomeschool"),
        model=model,
        memory=[]
    )

    return {"response": response}


@app.post("/ask/pdf")
async def ask_from_pdf(req: QueryRequest, request: Request):
    tableName = request.headers.get("table")
    token = request.headers.get("x-chat-token")
    username = request.headers.get("username")
    entity_key = request.headers.get("entity_key")

    if not token or not verify_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    if not username or not entity_key:
        raise HTTPException(status_code=400, detail="Missing username or entity_key")

    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        user_row = await conn.fetchrow(
            "SELECT id, query_count FROM users WHERE username = $1 AND entity_key = $2",
            username,
            entity_key,
        )
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        if user_row["query_count"] >= 25:
            raise HTTPException(status_code=403, detail="Query limit reached (25)")

        user_id = user_row["id"]

        ai = AiManager(provider=req.company.lower())
        pdf_table = f"{tableName}_pdf"

        db = Database(DB_CONFIG, api_key=OPENAI_API_KEY, table_name=pdf_table)

        try:
            results = await db.search_query(
                req.question,
                column_names=["text"],
                top_n=10
            )
            combined_context = "\n\n".join(
                f"{r.get('title', '')}\n{r.get('text', '')}" for r in results if 'text' in r
            ) if results else ""
        except Exception as e:
            logger.warning(f"PDF Search failed: {e}")
            combined_context = ""

        response = await ai.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=PERSONA_MAP.get(tableName),
            model=req.model,
            memory=[]
        )

        await conn.execute(
            "UPDATE users SET query_count = query_count + 1 WHERE id = $1",
            user_id
        )

        return {"response": response}
    finally:
        await conn.close()



@app.post("/ingest/url")
async def ingest_from_urls(req: Request):
    print("🔄 Ingestion request received")

    body = await req.json()
    urls = body.get("urls", [])
    table = "powellhomeschool"

    print(f"Urls: {urls}")
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        raise HTTPException(status_code=400, detail="URLs must be a list of strings")
    if not table:
        raise HTTPException(status_code=400, detail="Missing table name")

    table = re.sub(r'\W+', '', table.lower())
    content_type = 'urls'
    new_table_name = f"{table}_{content_type}"
    print(f"📋 Creating table: {new_table_name}")

    conn = await asyncpg.connect(**DB_CONFIG)

    print(f"✅ Table '{new_table_name}' created (or already exists)")

    # 🕒 Start timing
    print(f"🕸️ Starting scrape of {len(urls)} URLs...")
    start = time.perf_counter()
    records, rejected_urls = await scrape_urls(urls)
    scrape_duration = time.perf_counter() - start
    print(f"⏱️ Scrape completed in {scrape_duration:.2f} seconds")
    print(f"📄 Scraped {len(records)} pages")

    final_records = []
    for record in records:
        chunks = await dynamic_chunker(record)
        final_records.extend(chunks)
    print(f"📦 Total chunks prepared: {len(final_records)}")

    json_path = f"temp_{new_table_name}.json"
    async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(final_records, ensure_ascii=False))


    ingestion = DataIngestion(
        db_config=DB_CONFIG,
        api_key=OPENAI_API_KEY,
        table_name=new_table_name,
        column_names=["tag", "title", "text", "lookup"],
        embedding_columns=["text"],
        embed_from="text"
    )
    await ingestion.process_json_file(json_path)
    os.remove(json_path)
    print("✅ Ingestion complete and temp file removed")

    return {
        "status": "success",
        "table_created": new_table_name,
        "scrape_duration_sec": round(scrape_duration, 2),
        "rejected_urls": rejected_urls
    }


@app.post("/ingest/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    table: str = Header(...),
    title: str = Header(...),
    tag: str = Header(...),
    user_id: str = Header(None),
    x_chat_token: str = Header(None),
):

    """
    Endpoint to ingest a PDF file, extract text, chunk it, and store embeddings in the DB.
    """
    start_time = time.time()

    print("🔄 PDF ingestion request received")
    print(f"📄 Received file: {file.filename} for table: {table} (user: {user_id})")

    # Read binary content of the uploaded PDF
    contents = await file.read()

    # Temporarily save file to disk for PyMuPDF to open
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    # Extract text from PDF
    try:
        doc = fitz.open(tmp_path)
        extracted_text = "\n".join([page.get_text() for page in doc]).strip()
        doc.close()
    finally:
        os.remove(tmp_path)

    # Sanitize table name and prepare record
    table_name = f"{re.sub(r'\\W+', '', table.lower())}_pdf"
    record = {
        "tag":  tag,
        "title": title,
        "text": extracted_text,
    }

    # Initialize ingestion handler
    ingestion = DataIngestion(
        db_config=DB_CONFIG,
        api_key=OPENAI_API_KEY,
        table_name=table_name,
        column_names=["tag", "title", "text", "lookup"],
        embedding_columns=["text"],
        embed_from="text"
    )

    # Chunk and save to JSON
    chunks = await ingestion.dynamic_chunker(record)
    json_path = f"temp_{file.filename}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    # Process chunks into database
    await ingestion.process_json_file(json_path)
    os.remove(json_path)

    duration = round(time.time() - start_time, 2)
    print(f"duration: {duration}")
    return {
        "status": "success",
        "chunks": len(chunks),
        "table": table_name,
        "duration_seconds": duration
    }



class SignInRequest(BaseModel):
    username: str
    password: str
    entity_key: str


@app.post("/signin")
async def signin(req: SignInRequest):
    conn = await asyncpg.connect(**DB_CONFIG)
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1 AND password = $2 AND entity_key = $3",
        req.username,
        req.password,
        req.entity_key,
    )

    await conn.close()

    if row:
        token = get_current_token()
        return {
            "message": "Login successful",
            "token": token
        }

    raise HTTPException(status_code=401, detail="Invalid credentials or entity key")


models.Base.metadata.create_all(bind=database.engine)



def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/contact")
def submit_contact(form: schemas.ContactFormCreate, db: Session = Depends(get_db)):
    contact = models.ContactForm(**form.dict())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return {"message": "Contact form submitted successfully"}


#
