from google import genai
from google.genai import types
from .base import LLMClient


class GeminiClient(LLMClient):

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, json_retry_attempts: int = 2):
        super().__init__(model, max_tokens, json_retry_attempts)
        self.client = genai.Client(api_key=api_key)

    def _call(self, system: str, user: str) -> str:
        # Gemini combines system and user into a single prompt
        combined = f"{system}\n\n---\n\n{user}"
        response = self.client.models.generate_content(
            model=self.model,
            contents=combined,
            config=types.GenerateContentConfig(max_output_tokens=self.max_tokens),
        )
        return response.text
