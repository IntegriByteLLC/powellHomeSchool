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

        self.DB_CONFIG = {
            "user": os.getenv("DB_USER", "powellhomeschool"),
            "password": os.getenv("DB_PASS", "@powe!!homeschool2025"),
            "database": os.getenv("DB_NAME", "powellhomeschool"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 7894)),
        }

        self.MODEL_TOKEN_LIMITS = {
            "gpt-4": 8192,
            "gpt-4-0613": 8192,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-instruct": 4096,
            "gpt-3.5-turbo-instruct-0914": 4096,
            "gpt-3.5-turbo-1106": 16000,
            "gpt-3.5-turbo-0125": 16000,
            "default": 128000,
        }

        self.provider = AiManager(provider="gemini")
        self.chatModel = "gemini-1.5-flash-latest"

        self.PERSONA_MAP = {
            "powellhomeschool": (
                "You are an educational assistant for Powell HomeSchool. "
                "Use only the provided learning materials to answer questions. "
                "Do not guess or respond outside the scope of Powell HomeSchool content. "
                "If no relevant data is found, say: "
                "\"I can only respond based on Powell HomeSchool’s materials.\""
            )
        }

        self.db_pool = None  # pool initialized during startup
    async def init_db_pool(self):
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(**self.DB_CONFIG)
        return self.db_pool

    async def close_db_pool(self):
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None

config = Config()
