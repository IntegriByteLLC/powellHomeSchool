# main.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from powpow.database import Database
from Postgres.Routers import askRouter, pdfRouter, phonicsRouter, urlRouter, lessonRouter, usersRoute, \
    reloadPersonaRouter
from Postgres.config import config

from Postgres.databaseConnection import get_db_pool, init_db
from aiManager import AiManager

app = FastAPI()
db_tables: dict[str, Database] = {}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    config.db_pool = await get_db_pool()
    print("✅ Database initialized.")

    # Preload DB tables used for RAG
    TABLE_SUFFIXES = ["", "_pdf", "_urls"]
    async with config.db_pool.acquire() as conn:  # ensures pool is valid
        for suffix in TABLE_SUFFIXES:
            table = f"{config.BASE_TABLE}{suffix}"
            config.db_tables[table] = Database(
                db_config=config.DB_CONFIG,
                api_key=config.OPENAI_API_KEY,
                table_name=table,
                db_pool=config.db_pool
            )
            print(f"✅ Ensured table exists: {table}")

    # Pull persona + routing defaults from PowPow
    try:
        changed = await config.fetch_persona_from_powpow()
        print(f"✅ Persona loaded from PowPow (changed={changed}). "
              f"provider={config.default_provider}, model={config.default_model}")
    except Exception as e:
        print("⚠️ Failed to fetch persona from PowPow:", e)
        # We still start; routes will use local fallbacks.

    # Warm up chosen default provider/model
    try:
        ai = config.get_ai(config.default_provider)
        print(f"⏳ Warming up {config.default_provider}/{config.chatModel}...")
        await ai.ask(
            query="Hello, are you ready?",
            context_for_prompt="Reply with 'Ready'.",
            model=config.chatModel,
            persona="system"
        )
        print("✅ LLM warmed up and ready.")
    except Exception as e:
        print("⚠️ LLM warmup failed:", e)

@app.on_event("shutdown")
async def shutdown():
    await config.close_db_pool()

# Routers
app.include_router(pdfRouter.router)
app.include_router(urlRouter.router)
app.include_router(phonicsRouter.router)
app.include_router(askRouter.router)
app.include_router(lessonRouter.router)
app.include_router(usersRoute.router)
app.include_router(reloadPersonaRouter.control)
