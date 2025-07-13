from powpow.factory import get_assistant
from typing import List


class AIScrapeCleaner:
    def __init__(self, provider: str, db_config: dict, persona: str = ""):

        self.assistant = get_assistant(
            provider=provider,
        )

    async def clean(self, raw_html: str) -> str:
        prompt = (
            "Clean this web page content by removing only headers, footers, sidebars, navigation links, cookie notices, "
            "and any irrelevant repeated content. "
            "Do not paraphrase, rewrite, summarize, or modify the original text in any way. "
            "Return only the main body content **exactly as it appears**. "
            "Do not include emojis, icons, special characters, or markdown formatting. "
            "Preserve all original sentence structures, wording, punctuation, and line breaks from the main content.\n\n"
            "Keep events and useful info a user might find helpful"
            f"{raw_html}"
        )

        print("*************************************************************************************")
        cleaned_text = await self.assistant.get_response(
            query_text=prompt,
            model="gemini-1.5-flash",
            memory=[],
            context_for_prompt="Remove emojis, markdown (like bold or italic), and non-text symbols. Only return plain text paragraphs.",
        )
        return cleaned_text
