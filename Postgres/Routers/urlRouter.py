
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from powpow.ingestion import DataIngestion
from AutomateScraper.automateScrape import scrape_urls, dynamic_chunker
import aiofiles
import json
import os
import time
import re

from Postgres.config import config

router = APIRouter()

# @router.post("/ingest/url")
# async def ingest_from_urls(
#     request: Request,
# ):
#     print("🔄 Ingestion request received")
#
#     body = await request.json()
#     urls = body.get("urls", [])
#     table = "powellhomeschool"
#
#     print(f"Urls: {urls}")
#     if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
#         raise HTTPException(status_code=400, detail="URLs must be a list of strings")
#
#     table = re.sub(r'\W+', '', table.lower())
#     new_table_name = f"{table}_urls"
#     print(f"📋 Target table: {new_table_name}")
#
#     print(f"🕸️ Starting scrape of {len(urls)} URLs...")
#     start = time.perf_counter()
#     records, rejected_urls = await scrape_urls(urls)
#     scrape_duration = time.perf_counter() - start
#     print(f"⏱️ Scrape completed in {scrape_duration:.2f} seconds")
#     print(f"📄 Scraped {len(records)} pages")
#
#     final_records = []
#     for record in records:
#         chunks = await dynamic_chunker(record)
#         final_records.extend(chunks)
#     print(f"📦 Total chunks prepared: {len(final_records)}")
#
#     # Save to JSON temporarily
#     json_path = f"temp_{new_table_name}.json"
#     async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
#         await f.write(json.dumps(final_records, ensure_ascii=False))
#
#     # Ingest into vector DB (assumes powpow handles its own DB layer)
#     ingestion = DataIngestion(
#         db_config=config.DB_CONFIG,
#         api_key=config.OPENAI_API_KEY,
#         table_name=new_table_name,
#         column_names=["tag", "title", "text", "lookup"],
#         embedding_columns=["text"],
#         embed_from="text"
#     )
#     await ingestion.process_json_file(json_path)
#     os.remove(json_path)
#
#     print("✅ Ingestion complete and temp file removed")
#
#     return {
#         "status": "success",
#         "table_created": new_table_name,
#         "scrape_duration_sec": round(scrape_duration, 2),
#         "rejected_urls": rejected_urls
#     }
