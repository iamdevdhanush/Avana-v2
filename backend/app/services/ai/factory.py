import logging
from typing import List

from app.services.ai.base import AIProvider
from app.services.ai.gemini_provider import GeminiProvider, GeminiQuotaExceeded

logger = logging.getLogger(__name__)

_provider_instance = None


class FallbackProvider(AIProvider):
    """Chain multiple providers in order. Each fallback is tried on failure."""

    name = "fallback"

    @property
    def model_name(self) -> str:
        models = [p.model_name for p in self.providers if p.is_available()]
        return models[0] if models else "unknown"

    def __init__(self, providers: List[AIProvider]):
        self.providers = providers

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    def get_status(self) -> dict:
        statuses = {p.name: p.get_status() for p in self.providers}
        return {
            "provider": "fallback",
            "available": self.is_available(),
            "providers": statuses,
        }

    async def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        last_error = None
        for provider in self.providers:
            try:
                if not provider.is_available():
                    continue
                logger.info(f"[AI_FALLBACK] Trying provider: {provider.name}")
                result = await provider.generate(prompt, system_instruction)
                if result:
                    return result
            except GeminiQuotaExceeded as e:
                last_error = e
                logger.warning(f"[AI_FALLBACK] {provider.name} quota exceeded — trying next")
            except Exception as e:
                last_error = e
                logger.warning(f"[AI_FALLBACK] {provider.name} failed: {e} — trying next")
            continue
        if last_error:
            raise last_error
        return ""

    async def generate_structured(self, prompt: str, system_instruction: str) -> dict:
        last_error = None
        for provider in self.providers:
            try:
                if not provider.is_available():
                    continue
                logger.info(f"[AI_FALLBACK] Trying provider: {provider.name}")
                result = await provider.generate_structured(prompt, system_instruction)
                if result:
                    return result
            except GeminiQuotaExceeded as e:
                last_error = e
                logger.warning(f"[AI_FALLBACK] {provider.name} quota exceeded — trying next")
            except Exception as e:
                last_error = e
                logger.warning(f"[AI_FALLBACK] {provider.name} failed: {e} — trying next")
            continue
        if last_error:
            raise last_error
        return {}


def get_ai_provider() -> AIProvider:
    """Create or return the configured AI provider with fallback chain.
    
    Resolution order:
    1. If AI_PROVIDER=gemini → GeminiProvider only
    2. If AI_PROVIDER=openrouter → OpenRouterProvider only
    3. If AI_PROVIDER=auto (or unset) → Gemini → OpenRouter fallback
    4. If no key configured → returns a provider that reports unavailable
       (agents fall through to mock mode naturally)
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    from app.config import settings
    from app.services.ai.openrouter_provider import OpenRouterProvider

    provider_name = (settings.AI_PROVIDER or "auto").strip().lower()

    gemini = GeminiProvider()
    openrouter = OpenRouterProvider()

    if provider_name == "gemini":
        _provider_instance = gemini
    elif provider_name == "openrouter":
        _provider_instance = openrouter
    else:
        # auto: Gemini primary, OpenRouter fallback
        _provider_instance = FallbackProvider([gemini, openrouter])

    logger.info(f"[AI_FACTORY] Provider initialized: {_provider_instance.name}")
    return _provider_instance


def reset_ai_provider():
    """Reset the cached provider (useful for testing)."""
    global _provider_instance
    _provider_instance = None
