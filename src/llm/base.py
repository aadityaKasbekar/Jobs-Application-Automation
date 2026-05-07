import json
import time
from abc import ABC, abstractmethod


class LLMClient(ABC):

    def __init__(self, model: str, max_tokens: int = 4096, json_retry_attempts: int = 2):
        self.model = model
        self.max_tokens = max_tokens
        self.json_retry_attempts = json_retry_attempts

    @abstractmethod
    def _call(self, system: str, user: str) -> str:
        """Raw API call. Returns the response text."""

    def complete(self, system: str, user: str) -> str:
        return self._call(system, user)

    def complete_json(self, system: str, user: str) -> dict:
        """Call LLM and parse JSON response. Retries on parse failure."""
        last_error = None
        for attempt in range(self.json_retry_attempts + 1):
            raw = self._call(system, user)
            try:
                text = raw.strip()
                # Strip markdown code fences if the model adds them despite instructions
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text[: text.rfind("```")]
                return json.loads(text)
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < self.json_retry_attempts:
                    time.sleep(2)
        raise ValueError(
            f"LLM returned invalid JSON after {self.json_retry_attempts + 1} attempts. "
            f"Last error: {last_error}. Raw response (first 500 chars): {raw[:500]}"
        )
