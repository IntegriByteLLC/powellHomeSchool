import os
import asyncpg
from dotenv import load_dotenv
from aiManager import AiManager

load_dotenv()

class Config:
    def __init__(self):
        self.OPENAI_API_KEY = os.getenv("OPEN_API_KEY")
        self.MASTER_KEY = os.getenv("MASTER_API_KEY", "")
        self.JWT_SECRET = os.getenv("JWT_SECRET", "")
        self.JWT_ALGORITHM = "HS256"
        self.BASE_TABLE = os.getenv("BASE_TABLE", "powellhomeschool")
        self.db_tables = {}
        self.ai_manager = None   # ✅ Will hold global AiManager instance

        self.DB_CONFIG = {
            "user": os.getenv("DB_USER", "powellhomeschool"),
            "password": os.getenv("DB_PASS", "@powe!!homeschool2025"),
            "database": os.getenv("DB_NAME", "powellhomeschool"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 7894)),
        }

        self.MODEL_TOKEN_LIMITS = {
            "gemini-2.0-flash": 128000,
            "gemini-2.0-flash-lite": 128000,
            "default": 128000,
        }

        self.chatModel = "gemini-2.0-flash"   # ✅ switched to faster model

        self.PERSONA_MAP = {
            "powellhomeschool": (
                "You are an educational assistant for Powell HomeSchool. "
                "Use only the provided learning materials to answer questions. "
                "say what you need to sain in under 25 words"


            )
        }

        self.db_pool = None

    async def init_db_pool(self):
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(**self.DB_CONFIG)
        return self.db_pool

    async def close_db_pool(self):
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None

config = Config()
