# Postgres/config.py
import os
import asyncpg
import httpx
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
        self.DB_CONFIG = {
            "user": os.getenv("DB_USER", "powellhomeschool"),
            "password": os.getenv("DB_PASS", "@powe!!homeschool2025"),
            "database": os.getenv("DB_NAME", "powellhomeschool"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 7894)),
        }

        # PowPow control-plane
        self.POWPOW_URL = os.getenv("POWPOW_URL", "https://powpow.integri-byte.com")
        self.COMPANY_ID = os.getenv("COMPANY_ID", "")
        self.POWPOW_API_KEY = os.getenv("POWPOW_API_KEY", self.MASTER_KEY)

        # Cached persona/config (filled on startup)
        self.persona_text: str | None = None
        self.persona_data: dict = {}
        self.default_provider: str | None = None
        self.default_model: str | None = None
        self.persona_version: int | None = None
        self.persona_etag: str | None = None

        # LLM + DB helpers
        self.MODEL_TOKEN_LIMITS = {
            "gemini-2.0-flash": 128000,
            "gemini-2.0-flash-lite": 128000,
            "default": 128000,
        }
        self.chatModel = "gemini-2.0-flash"     # fallback if PowPow doesn’t set a model
        self.db_tables: dict[str, object] = {}
        self.db_pool = None
        self.ai_managers: dict[str, AiManager] = {}

    async def init_db_pool(self):
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(**self.DB_CONFIG)
        return self.db_pool

    async def close_db_pool(self):
        if self.db_pool:
            await self.db_pool.close()
            self.db_pool = None

    def get_ai(self, provider: str | None):
        key = (provider or "gemini").lower()
        if key not in self.ai_managers:
            self.ai_managers[key] = AiManager(provider=key)
        return self.ai_managers[key]

    async def fetch_persona_from_powpow(self) -> bool:
        """
        Pull the latest persona/provider/model from the PowPow server.
        Uses ETag to avoid needless reloads.
        Returns True if updated, False if not changed.
        """
        if not self.COMPANY_ID:
            raise RuntimeError("COMPANY_ID is not set")

        url = f"{self.POWPOW_URL.rstrip('/')}/persona/companies/{self.COMPANY_ID}/persona"
        headers = {"Accept": "application/json"}
        if self.POWPOW_API_KEY:
            headers["x-api-key"] = self.POWPOW_API_KEY
        if self.persona_etag:
            headers["If-None-Match"] = self.persona_etag

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 304:
                return False
            resp.raise_for_status()
            data = resp.json()

        self.persona_version = data.get("version")
        self.persona_data = data.get("data") or {}
        self.persona_text = (
            data.get("persona")
            or self.persona_data.get("system_prompt")
            or "You are a helpful assistant."
        )
        self.default_provider = data.get("provider") or self.default_provider or "gemini"
        self.default_model = data.get("model") or self.default_model or self.chatModel
        self.persona_etag = resp.headers.get("etag")

        # Keep chatModel aligned with PowPow’s default model (fallback preserved)
        self.chatModel = self.default_model or self.chatModel
        return True

config = Config()
