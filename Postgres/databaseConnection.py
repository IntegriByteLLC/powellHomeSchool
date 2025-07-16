# Postgres/db_connection.py

import os

from asyncpg import create_pool
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from Postgres.config import config
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()
Base = declarative_base()
# Get DB URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")
pool = None
# Create the async engine
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=True,  # set to False in production
)

# Create session factory
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)



async def get_db_pool():
    global pool
    if pool is None:
        pool = await create_pool(
            user=config.DB_CONFIG["user"],
            password=config.DB_CONFIG["password"],
            database=config.DB_CONFIG["database"],
            host=config.DB_CONFIG["host"],
            port=config.DB_CONFIG["port"],
            min_size=2,
            max_size=10
        )
    return pool

# Optional startup hook to create tables and UUID extension
async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)



async def get_db():
    async with AsyncSessionLocal() as session:
        yield session