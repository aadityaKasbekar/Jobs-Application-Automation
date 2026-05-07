from openai import OpenAI
from .base import LLMClient


class OpenAIClient(LLMClient):

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, json_retry_attempts: int = 2):
        super().__init__(model, max_tokens, json_retry_attempts)
        self.client = OpenAI(api_key=api_key)

    def _call(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content
