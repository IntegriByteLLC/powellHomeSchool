# Postgres/Routers/askRouter.py
from fastapi import APIRouter, HTTPException, Request
import asyncio, time, logging
from Postgres.config import config
from Postgres.schemas import QueryRequest
from Utils.utils import estimate_tokens
from powpow.database import Database

router = APIRouter(prefix="/ask", tags=["Ask"])
logger = logging.getLogger(__name__)

@router.post("")
async def ask_question(req: QueryRequest, request: Request):
    logger.info("Tenant /ask received: provider=%r model=%r", req.provider, req.model)
    # Use client overrides if provided; else use PowPow defaults loaded at startup
    provider = (req.provider or config.default_provider or "gemini").lower()
    model = req.model or config.default_model or config.chatModel
    ai = config.get_ai(provider)

    overall_start = time.monotonic()
    db_start = time.monotonic()

    try:
        combined_context = ""
        # fan-out to table variants
        suffixes = ["", "_pdf", "_urls"]
        tasks = []
        for suffix in suffixes:
            table_name = f"{config.BASE_TABLE}{suffix}"
            db_instance: Database | None = config.db_tables.get(table_name)
            if db_instance:
                tasks.append(db_instance.search_query(req.question, column_names=["title", "text"], top_n=5))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # ✅ correct flatten + ignore failures
        total_results = []
        for idx, res in enumerate(all_results):
            if isinstance(res, Exception):
                logger.warning("Task %s failed: %s", idx, res)
                continue
            if isinstance(res, list):
                total_results.extend(res)
            else:
                logger.warning("Task %s returned %r (expected list)", idx, type(res))

        db_elapsed = round((time.monotonic() - db_start) * 1000, 2)

        if total_results:
            combined_context = "\n\n".join(
                f"{r.get('title', '')}\n{r.get('text', '')}" for r in total_results if 'text' in r
            )

        token_limit = config.MODEL_TOKEN_LIMITS.get(model, config.MODEL_TOKEN_LIMITS["default"])
        if estimate_tokens(combined_context) > token_limit - 1000:
            combined_context = config.trim_context(combined_context, token_limit - 1000)

        # ✅ Persona comes from PowPow (cached in memory)
        llm_response = await ai.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=config.persona_text or "You are a helpful assistant.",
            model=model,
            memory=[]
        )

        total_elapsed = round((time.monotonic() - overall_start) * 1000, 2)
        return {"response": llm_response, "metrics": {"db_search_ms": db_elapsed, "total_response_ms": total_elapsed}}

    except Exception as e:
        logger.warning(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/chat")
async def ask_chat(req: QueryRequest, request: Request):
    # Chat uses the global defaults entirely (no override)
    overall_start = time.monotonic()
    db_start = time.monotonic()

    try:
        combined_context = ""
        suffixes = ["", "_pdf", "_urls"]
        tasks = []
        for suffix in suffixes:
            table_name = f"{config.BASE_TABLE}{suffix}"
            db_instance: Database | None = config.db_tables.get(table_name)
            if db_instance:
                tasks.append(
                    db_instance.search_query(
                        req.question, column_names=["title", "text"], top_n=5
                    )
                )

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # ✅ Fix: correctly flatten results and ignore failed tasks
        total_results = []
        for idx, res in enumerate(all_results):
            if isinstance(res, Exception):
                logger.warning("Task %s failed: %s", idx, res)
                continue
            if isinstance(res, list):
                total_results.extend(res)
            else:
                logger.warning("Task %s returned %r (expected list)", idx, type(res))

        db_elapsed = round((time.monotonic() - db_start) * 1000, 2)

        if total_results:
            parts = []
            for row in total_results:
                text = row.get("text")
                if not text:
                    continue
                title = row.get("title", "")
                parts.append(f"{title}\n{text}" if title else text)
            combined_context = "\n\n".join(parts)

        token_limit = config.MODEL_TOKEN_LIMITS.get(
            config.chatModel, config.MODEL_TOKEN_LIMITS["default"]
        )
        if estimate_tokens(combined_context) > token_limit - 1000:
            combined_context = config.trim_context(combined_context, token_limit - 1000)

        ai = config.get_ai(config.default_provider or "gemini")
        llm_response = await ai.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=config.persona_text or "You are a helpful assistant.",
            model=config.chatModel,
            memory=[],
        )

        total_elapsed = round((time.monotonic() - overall_start) * 1000, 2)
        return {
            "response": llm_response,
            "metrics": {
                "db_search_ms": db_elapsed,
                "total_response_ms": total_elapsed,
            },
        }

    except Exception as e:
        logger.warning(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/pdf")
async def ask_from_pdf(req: QueryRequest, request: Request):
    # If you still gate with token, keep your verify_token here; omitted in your snippet.
    overall_start = time.monotonic()

    try:
        pdf_table = f"{config.BASE_TABLE}_pdf"
        db: Database | None = config.db_tables.get(pdf_table)
        if not db:
            raise HTTPException(status_code=500, detail="PDF index not available")

        results = await db.search_query(req.question, column_names=["text"], top_n=10)
        combined_context = "\n\n".join(
            f"{r.get('title', '')}\n{r.get('text', '')}" for r in results if 'text' in r
        ) if results else ""

        provider = (req.provider or config.default_provider or "gemini").lower()
        model = req.model or config.default_model or config.chatModel
        ai = config.get_ai(provider)

        response = await ai.ask(
            query=req.question,
            context_for_prompt=combined_context,
            persona=config.persona_text or "You are a helpful assistant.",
            model=model,
            memory=[]
        )
        return {"response": response}

    except Exception as e:
        logger.warning(f"PDF Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
