from .base import LLMClient
from .claude_client import ClaudeClient
from .openai_client import OpenAIClient
from .gemini_client import GeminiClient

PROVIDERS = {
    "claude": ClaudeClient,
    "openai": OpenAIClient,
    "gemini": GeminiClient,
}

DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-1.5-pro",
}


def create_client(
    provider: str,
    api_key: str,
    model: str | None = None,
    max_tokens: int = 4096,
    json_retry_attempts: int = 2,
) -> LLMClient:
    provider = provider.lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(PROVIDERS)}")
    resolved_model = model or DEFAULT_MODELS[provider]
    return PROVIDERS[provider](
        api_key=api_key,
        model=resolved_model,
        max_tokens=max_tokens,
        json_retry_attempts=json_retry_attempts,
    )
