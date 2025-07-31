from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from Postgres.config import config
from Postgres.schemas import QueryRequest
from Utils.utils import verify_token, estimate_tokens
from aiManager import AiManager
from powpow.database import Database

import time
import logging

router = APIRouter(prefix="/ask", tags=["Ask"])
logger = logging.getLogger(__name__)

@router.post("")
async def ask_question(req: QueryRequest, request: Request):
    provider = req.company.lower()
    model = req.model
    ai = AiManager(provider=provider)

    overall_start = time.monotonic()
    db_start = time.monotonic()

    try:
        combined_context = ""
        total_results = []

        suffixes = ["", "_pdf", "_urls"]
        tasks = []

        for suffix in suffixes:
            table_name = f"{config.BASE_TABLE}{suffix}"
            db_instance = config.db_tables.get(table_name)
            if db_instance:
                tasks.append(db_instance.search_query(req.question, column_names=["title", "text"], top_n=5))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_results = [r for sublist in all_results if isinstance(sublist, list) for r in sublist]

        db_elapsed = round((time.monotonic() - db_start) * 1000, 2)  # milliseconds

        if total_results:
            combined_context = "\n\n".join(
                f"{r.get('title', '')}\n{r.get('text', '')}" for r in total_results if 'text' in r
            )

        token_limit = config.MODEL_TOKEN_LIMITS.get(model, config.MODEL_TOKEN_LIMITS["default"])
        if estimate_tokens(combined_context) > token_limit - 1000:
            combined_context = config.trim_context(combined_context, token_limit - 1000)

        llm_response = await ai.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=config.PERSONA_MAP.get(req.company.lower(), config.PERSONA_MAP["powellhomeschool"]),
            model=model,
            memory=[]
        )

        total_elapsed = round((time.monotonic() - overall_start) * 1000, 2)  # milliseconds
        print(f"Time for db: {db_elapsed}")
        return {
            "response": llm_response,
            "metrics": {
                "db_search_ms": db_elapsed,
                "total_response_ms": total_elapsed
            }
        }

    except Exception as e:
        logger.warning(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat")
async def ask_question(req: QueryRequest, request: Request):
    overall_start = time.monotonic()
    db_start = time.monotonic()

    try:
        combined_context = ""
        total_results = []

        suffixes = ["", "_pdf", "_urls"]
        tasks = []

        for suffix in suffixes:
            table_name = f"{config.BASE_TABLE}{suffix}"
            db_instance = config.db_tables.get(table_name)
            if db_instance:
                tasks.append(db_instance.search_query(req.question, column_names=["title", "text"], top_n=5))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_results = [r for sublist in all_results if isinstance(sublist, list) for r in sublist]

        db_elapsed = round((time.monotonic() - db_start) * 1000, 2)  # milliseconds

        if total_results:
            combined_context = "\n\n".join(
                f"{r.get('title', '')}\n{r.get('text', '')}" for r in total_results if 'text' in r
            )

        token_limit = config.MODEL_TOKEN_LIMITS.get(config.chatModel, config.MODEL_TOKEN_LIMITS["default"])
        if estimate_tokens(combined_context) > token_limit - 1000:
            combined_context = config.trim_context(combined_context, token_limit - 1000)

        llm_response = await config.ai_manager.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=config.PERSONA_MAP.get("powellhomeschool"),
            model=config.chatModel,
            memory=[]
        )

        print(llm_response)
        total_elapsed = round((time.monotonic() - overall_start) * 1000, 2)  # milliseconds
        print(f"Time for db: {db_elapsed}")
        return {
            "response": llm_response,
            "metrics": {
                "db_search_ms": db_elapsed,
                "total_response_ms": total_elapsed
            }
        }

    except Exception as e:
        logger.warning(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/pdf")
async def ask_from_pdf(req: QueryRequest, request: Request):
    token = request.headers.get("x-chat-token")
    username = request.headers.get("username")
    entity_key = request.headers.get("entity_key")

    if not token or not verify_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    if not username or not entity_key:
        raise HTTPException(status_code=400, detail="Missing username or entity_key")

    try:
        async with config.db_pool.acquire() as conn:
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

            pdf_table = f"{config.BASE_TABLE}_pdf"
            db = Database(
                config.DB_CONFIG,
                api_key=config.OPENAI_API_KEY,
                table_name=pdf_table,
                db_pool=config.db_pool
            )

            results = await db.search_query(req.question, column_names=["text"], top_n=10)
            combined_context = "\n\n".join(
                f"{r.get('title', '')}\n{r.get('text', '')}" for r in results if 'text' in r
            ) if results else ""

            response = await ai.ask(
                query=req.question,
                context_for_prompt=combined_context,
                persona=config.PERSONA_MAP.get(config.BASE_TABLE),
                model=req.model,
                memory=[]
            )

            await conn.execute(
                "UPDATE users SET query_count = query_count + 1 WHERE id = $1",
                user_id
            )

            return {"response": response}

    except Exception as e:
        logger.warning(f"PDF Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
