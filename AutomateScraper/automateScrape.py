import os
import re
import json
import asyncio
from typing import Any, Coroutine

import pandas as pd

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from powpow.ingestion import DataIngestion

from AutomateScraper.ai_scrape_cleaner import AIScrapeCleaner
from Postgres.config import Config

# --- Load env vars ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPEN_API_KEY")



persona = "You are a professional web content cleaner. Remove all headers, footers, navigation menus, and irrelevant noise like links, cookie popups, social media buttons, and policy disclaimers. Return only the main body content, formatted cleanly."

TABLE_NAME = "lcraTest"
config = Config()

aiCleaner = AIScrapeCleaner(provider='gemini',db_config=config.DB_CONFIG)


# --- Chunker ---
async def dynamic_chunker(record, max_tokens=8192):
    text = record["text"]
    token_estimate = len(text) // 4
    if token_estimate <= max_tokens:
        return [record]

    n_chunks = min(12, max(2, token_estimate // 8192 + 1))
    segments = re.split(r'(?<=[.?!])\s+|\n{2,}', text)
    chunk_size = len(segments) // n_chunks
    group_id = record["url"]

    chunks = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = None if i == n_chunks - 1 else (i + 1) * chunk_size
        chunk_text = " ".join(segments[start:end])
        cleaned_chunk = await run_cleaner(chunk_text)
        chunks.append({
            "url": record["url"],
            "title": f"{record['title']} (Part {i + 1})",
            "text": cleaned_chunk.strip(),
            "group_id": group_id,
            "part": i + 1
        })

    return chunks

# --- Scraper ---
async def scrape_urls(urls: list[str]) -> tuple[list[Any], list[Any]]:
    results = []
    rejected = []  # 🔴 Add this
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for idx, url in enumerate(urls, 1):
            try:
                print(f"➡️ ({idx}/{len(urls)}) Scraping: {url}")
                await page.goto(url, timeout=60000)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                body_text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""

                if any(bad in title.lower() for bad in ["404", "access denied", "not found", "forbidden"]):
                    reason = f"⚠️ Rejected '{url}': error-like title → '{title}'"
                    print(reason)
                    rejected.append({"url": url, "reason": "error title", "title": title})
                    continue

                if not body_text.strip():
                    reason = f"⚠️ Rejected '{url}': empty body content"
                    print(reason)
                    rejected.append({"url": url, "reason": "empty body", "title": title})
                    continue

                lines = body_text.splitlines()
                cleaned_lines = [
                    line for line in lines
                    if not any(kw.lower() in line.lower() for kw in [
                        "cookie", "contact", "privacy", "search", "subscribe", "footer"
                    ])
                ]
                precleaned = "\n".join(cleaned_lines)
                cleaned = await aiCleaner.clean(precleaned)
                results.append({"url": url, "title": title, "text": cleaned})
                print("✅ Success")
            except Exception as e:
                print(f"❌ Failed: {url}\n   Error: {e}")
                rejected.append({"url": url, "reason": f"exception: {e}"})

        await browser.close()
    return results, rejected


#----Ai cleaner------
async def run_cleaner(text: str) -> str:
    cleaner = AIScrapeCleaner()
    return await cleaner.clean(text)


# --- Main Runner ---
async def main():
    # You can later replace this with a parameter from Flutter/API
    urls = [
        'https://www.lcra.org/about/',
        'https://www.lcra.org/news/',
        'https://www.lcra.org/careers/',
    ]

    records = await scrape_urls(urls)

    # Apply chunking
    final_records = []
    for record in records:
        chunks = await dynamic_chunker(record)
        final_records.extend(chunks)

    # Save to temp JSON
    json_path = "temp_scraped_records.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_records, f, ensure_ascii=False)

    # PowPow ingestion
    ingestion = DataIngestion(
        db_config=DB_CONFIG,
        api_key=OPENAI_API_KEY,
        table_name=TABLE_NAME,
        column_names=["url", "title", "text", "lookup"],
        embedding_columns=["text"],
        embed_from="text"
    )
    await ingestion.process_json_file(json_path)
    os.remove(json_path)
    print("✅ Ingestion complete")

if __name__ == "__main__":
    asyncio.run(main())
