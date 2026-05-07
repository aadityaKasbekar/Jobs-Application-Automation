import anthropic
from .base import LLMClient


class ClaudeClient(LLMClient):

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096, json_retry_attempts: int = 2):
        super().__init__(model, max_tokens, json_retry_attempts)
        self.client = anthropic.Anthropic(api_key=api_key)

    def _call(self, system: str, user: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
