# aiManager.py
from powpow.factory import get_assistant
from powpow.openai_assistant import OpenAIAssistant
from powpow.config import Config
from powpow.logger import logger,enable_debug
from powpow.processor import Processor
from powpow.database import Database
from powpow.ingestion import DataIngestion
from typing import List, Optional

from sympy.physics.units import temperature


class AiManager:
    def __init__(self, provider: str):

        self.assistant = get_assistant(
            provider=provider,
        )

        self.assistant_Llama = get_assistant(
            provider="llama",
        )

    async def ask(
        self,

        query: str,
        context_for_prompt: str,
        model: str,
        persona: str,
        memory: Optional[List[str]] = None,
        column_names: Optional[List[str]] = None,
        top_n: int = 20,
    ) -> str:

        return await self.assistant.get_response(
            query_text=query,
            context_for_prompt=context_for_prompt,
            model=model,
            memory=memory or [],
            persona=persona,

        )
    async def complete_json(self, prompt: str, max_tokens: int = 600) -> str:
        return await self.assistant.get_response(
            query_text=prompt,
            context_for_prompt="You are a helpful AI tutor that returns JSON formatted flashcards.",
            model="gemini-2.0-flash",
            memory=[],
            persona="educator",
        )
