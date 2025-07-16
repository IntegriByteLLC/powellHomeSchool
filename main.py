# main.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from powpow.database import Database
from Postgres.Routers import askRouter, pdfRouter, phonicsRouter, urlRouter, lessonRouter
from Postgres.config import config

from Postgres.databaseConnection import get_db_pool, init_db

app = FastAPI()
db_tables: dict[str, Database] = {}  # Temporary storage for runtime use


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

    await config.init_db_pool()
    async with config.db_pool.acquire() as conn:
        for suffix in TABLE_SUFFIXES:
            table = f"{config.BASE_TABLE}{suffix}"
            config.db_tables[table] = Database(
                db_config=config.DB_CONFIG,
                api_key=config.OPENAI_API_KEY,
                table_name=table,
                db_pool=config.db_pool
            )
            print(f"✅ Ensured table exists: {table}")

@app.on_event("shutdown")
async def shutdown():
    await config.close_db_pool()

# Routers
app.include_router(pdfRouter.router)
app.include_router(urlRouter.router)
app.include_router(phonicsRouter.router)
app.include_router(askRouter.router)
app.include_router(lessonRouter.router)
