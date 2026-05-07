import google.generativeai as genai
from .base import LLMClient


class GeminiClient(LLMClient):

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, json_retry_attempts: int = 2):
        super().__init__(model, max_tokens, json_retry_attempts)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(
            model_name=model,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
        )

    def _call(self, system: str, user: str) -> str:
        # Gemini combines system and user into a single prompt
        combined = f"{system}\n\n---\n\n{user}"
        response = self.client.generate_content(combined)
        return response.text
