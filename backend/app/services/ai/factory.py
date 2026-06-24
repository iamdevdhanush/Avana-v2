import logging
from typing import List, Optional

from app.services.ai.base import AIProvider
from app.services.ai.gemini_provider import GeminiProvider, GeminiQuotaExceeded

logger = logging.getLogger(__name__)

_provider_instance = None
_provider_config: Optional[dict] = None

_fallback_events: List[dict] = []


def get_fallback_events() -> List[dict]:
    return list(_fallback_events)


class FallbackProvider(AIProvider):
    """Chain multiple providers in order. Each fallback is tried on failure.
    
    Fallback chain: OpenRouter -> Gemini -> Mock (implicit)
    All fallbacks are logged for observability.
    """

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

    def _log_fallback(self, provider_name: str, model: str, success: bool, error: Optional[str] = None):
        event = {
            "provider": provider_name,
            "model": model,
            "success": success,
            "error": error,
        }
        _fallback_events.append(event)
        if len(_fallback_events) > 1000:
            _fallback_events.pop(0)
        if success:
            logger.info(f"[AI_FALLBACK] Success: provider={provider_name} model={model}")
        else:
            logger.warning(f"[AI_FALLBACK] Failure: provider={provider_name} error={error}")

    async def generate(self, prompt: str, system_instruction: str | None = None) -> str:
        last_error = None
        for provider in self.providers:
            try:
                if not provider.is_available():
                    logger.info(f"[AI_FALLBACK] Skipping unavailable provider: {provider.name}")
                    continue
                logger.info(f"[AI_FALLBACK] Trying provider: {provider.name} model={provider.model_name}")
                result = await provider.generate(prompt, system_instruction)
                if result:
                    self._log_fallback(provider.name, provider.model_name, True)
                    return result
                self._log_fallback(provider.name, provider.model_name, False, "Empty response")
            except GeminiQuotaExceeded as e:
                last_error = e
                self._log_fallback(provider.name, provider.model_name, False, f"Quota exceeded: {e}")
                logger.warning(f"[AI_FALLBACK] {provider.name} quota exceeded — trying next")
            except Exception as e:
                last_error = e
                self._log_fallback(provider.name, provider.model_name, False, str(e))
                logger.warning(f"[AI_FALLBACK] {provider.name} failed: {e} — trying next")
            continue
        if last_error:
            logger.error(f"[AI_FALLBACK] All providers failed. Last error: {last_error}")
            raise last_error
        logger.error("[AI_FALLBACK] No providers available and no error captured")
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
                    self._log_fallback(provider.name, provider.model_name, True)
                    return result
            except GeminiQuotaExceeded as e:
                last_error = e
                self._log_fallback(provider.name, provider.model_name, False, f"Quota exceeded: {e}")
                logger.warning(f"[AI_FALLBACK] {provider.name} quota exceeded — trying next")
            except Exception as e:
                last_error = e
                self._log_fallback(provider.name, provider.model_name, False, str(e))
                logger.warning(f"[AI_FALLBACK] {provider.name} failed: {e} — trying next")
            continue
        if last_error:
            logger.error(f"[AI_FALLBACK] All providers failed for structured generation. Last error: {last_error}")
            raise last_error
        return {}


def _build_provider_from_config(config: dict) -> AIProvider:
    from app.services.ai.openrouter_provider import OpenRouterProvider

    provider_name = config["provider"].strip().lower()
    model = config["model"]
    api_key = config["api_key"]

    if provider_name == "gemini":
        return GeminiProvider(api_key=api_key, model_name=model)
    elif provider_name == "openrouter":
        return OpenRouterProvider(api_key=api_key, model=model)
    elif provider_name == "auto":
        gemini = GeminiProvider(api_key=api_key, model_name="gemini-2.0-flash")
        openrouter = OpenRouterProvider(api_key=api_key, model=model)
        return FallbackProvider([openrouter, gemini])
    raise ValueError(f"Unknown provider: {provider_name}")


async def _load_db_config() -> Optional[dict]:
    try:
        from app.database import get_engine
        from app.utils.encryption import decrypt_api_key
        from sqlalchemy import text as sa_text

        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                sa_text("""
                    SELECT provider, model, encrypted_api_key
                    FROM ai_provider_configs
                    WHERE is_active = true
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            if row:
                return {
                    "provider": row[0],
                    "model": row[1],
                    "api_key": decrypt_api_key(row[2]),
                }
    except Exception as e:
        logger.warning(f"[AI_FACTORY] Could not load DB config: {e}")
    return None


def set_db_provider_config(config: Optional[dict]):
    global _provider_config
    _provider_config = config


def get_db_provider_config() -> Optional[dict]:
    return _provider_config


def get_ai_provider() -> AIProvider:
    """Create or return the configured AI provider with fallback chain.

    Resolution order:
    1. Database active config (if set via set_db_provider_config)
    2. Environment variables (AI_PROVIDER, OPENROUTER_API_KEY, etc.)
    3. If no key configured → returns a provider that reports unavailable
       (agents fall through to mock mode naturally)
    
    Fallback order: OpenRouter -> Gemini -> Mock
    """
    from app.utils.timing import Timer

    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    with Timer("6. AI provider initialization"):
        from app.config import settings
        from app.services.ai.openrouter_provider import OpenRouterProvider

        db_config = _provider_config
        if db_config:
            logger.info(f"[AI_FACTORY] Using database config: provider={db_config['provider']} model={db_config['model']}")
            _provider_instance = _build_provider_from_config(db_config)
            logger.info(f"[AI_FACTORY] DB provider online: {_provider_instance.name} model={_provider_instance.model_name}")
            return _provider_instance

        provider_name = (settings.AI_PROVIDER or "auto").strip().lower()

        gemini = GeminiProvider()
        openrouter = OpenRouterProvider()

        logger.info(
            f"[AI_FACTORY] Env config: AI_PROVIDER={provider_name} "
            f"OPENROUTER_API_KEY={'set' if settings.OPENROUTER_API_KEY else 'unset'} "
            f"GEMINI_API_KEY={'set' if settings.GEMINI_API_KEY else 'unset'} "
            f"openrouter_available={openrouter.is_available()} "
            f"gemini_available={gemini.is_available()}"
        )

        if provider_name == "gemini":
            _provider_instance = gemini
        elif provider_name == "openrouter":
            _provider_instance = openrouter
        else:
            _provider_instance = FallbackProvider([openrouter, gemini])

        logger.info(
            f"[AI_FACTORY] Provider initialized: {_provider_instance.name} "
            f"model={_provider_instance.model_name} "
            f"available={_provider_instance.is_available()}"
        )
        return _provider_instance


def reset_ai_provider():
    """Reset the cached provider (useful for testing or config change)."""
    global _provider_instance, _fallback_events
    _provider_instance = None
    _fallback_events.clear()


def get_ai_fallback_events() -> List[dict]:
    """Return recorded fallback events for observability."""
    return list(_fallback_events)
