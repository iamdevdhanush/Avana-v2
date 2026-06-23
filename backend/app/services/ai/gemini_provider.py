import json
import logging
import re
import time
from typing import Optional

from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

QUOTA_COOLDOWN_MINUTES = 15


class GeminiQuotaExceeded(Exception):
    pass


class GeminiAuthError(Exception):
    pass


class GeminiProvider(AIProvider):
    name = "gemini"

    @property
    def model_name(self) -> str:
        return "gemini-2.0-flash"

    def __init__(self):
        self.api_key = None
        self.model = None
        self._last_call_time = 0
        self._call_count_this_minute = 0
        self._minute_start = time.time()
        self._available = False
        self._init_error = None
        self._quota_until = None
        self._init()

    def _init(self):
        from app.config import settings
        api_key = settings.GEMINI_API_KEY
        logger.info(f"[GEMINI] Init. Key present: {bool(api_key)}")
        if not api_key:
            self._available = False
            self._init_error = "GEMINI_API_KEY not configured"
            logger.warning(f"[GEMINI] {self._init_error}")
            return
        if len(api_key) < 10:
            self._available = False
            self._init_error = f"GEMINI_API_KEY too short (len={len(api_key)})"
            logger.error(f"[GEMINI] {self._init_error}")
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.api_key = api_key
            self._available = True
            logger.info("[GEMINI] Gemini service initialized — ONLINE")
        except Exception as e:
            self._available = False
            self._init_error = f"Gemini init failed: {type(e).__name__}: {e}"
            logger.error(f"[GEMINI] {self._init_error}")

    def is_available(self) -> bool:
        if self._quota_until and time.time() < self._quota_until:
            return False
        return self._available

    def get_unavailable_reason(self) -> Optional[str]:
        if self._quota_until and time.time() < self._quota_until:
            return "QUOTA_EXCEEDED"
        if not self._available:
            return "OFFLINE"
        return None

    def get_status(self) -> dict:
        status = {
            "provider": "gemini",
            "model": "gemini-2.0-flash" if self._available else None,
            "has_api_key": bool(self.api_key),
            "init_error_detail": self._init_error,
        }
        if self._quota_until and time.time() < self._quota_until:
            remaining = int(self._quota_until - time.time())
            status["available"] = False
            status["status"] = "QUOTA_EXCEEDED"
            status["error"] = "Gemini API quota exceeded"
            status["retry_after_seconds"] = remaining
        elif not self._available:
            status["available"] = False
            status["status"] = "OFFLINE"
            status["error"] = self._init_error or "Gemini unavailable"
        else:
            status["available"] = True
            status["status"] = "ONLINE"
            status["error"] = None
        return status

    def _check_rate_limit(self):
        now = time.time()
        if now - self._minute_start >= 60:
            self._call_count_this_minute = 0
            self._minute_start = now
        if self._call_count_this_minute >= 50:
            raise GeminiQuotaExceeded("Gemini free tier rate limit approached (50/min)")
        self._call_count_this_minute += 1
        elapsed = now - self._last_call_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_call_time = time.time()

    def _is_transient(self, err: Exception) -> bool:
        err_str = str(err).lower()
        return any(k in err_str for k in ["429", "503", "timeout", "rate", "internal", "unavailable", "deadline"])

    async def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        logger.info("[GEMINI] generate() called")

        if not self._available:
            logger.warning(f"[GEMINI] Unavailable: {self._init_error}")
            return ""
        if self._quota_until and time.time() < self._quota_until:
            remaining = int(self._quota_until - time.time())
            logger.warning(f"[GEMINI] Quota cooldown — {remaining}s remaining")
            raise GeminiQuotaExceeded(f"Gemini quota cooldown — retry in {remaining}s")

        import google.generativeai as genai
        import asyncio

        loop = asyncio.get_event_loop()

        def _sync_generate():
            for attempt in range(1, 4):
                try:
                    self._check_rate_limit()
                    if system_instruction:
                        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=system_instruction)
                    else:
                        model = self.model
                    response = model.generate_content(prompt, request_options={"retry": None})
                    if not response or not response.text:
                        logger.warning("[GEMINI] Empty response")
                        return ""
                    logger.info(f"[GEMINI] Response ({len(response.text)} chars)")
                    return response.text
                except GeminiQuotaExceeded:
                    raise
                except Exception as e:
                    err_str = str(e)
                    if "API_KEY_INVALID" in err_str or "API key" in err_str:
                        self._available = False
                        self._init_error = "Gemini API key invalid or rejected"
                        logger.error(f"[GEMINI] {self._init_error}")
                        raise GeminiAuthError(self._init_error) from e
                    if "ACCESS_TOKEN_TYPE_UNSUPPORTED" in err_str:
                        self._available = False
                        self._init_error = "Gemini received OAuth token instead of API key"
                        logger.error(f"[GEMINI] {self._init_error}")
                        raise GeminiAuthError(self._init_error) from e
                    if "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                        logger.error(f"[GEMINI] Quota exhausted: {e}")
                        self._quota_until = time.time() + QUOTA_COOLDOWN_MINUTES * 60
                        raise GeminiQuotaExceeded(f"Gemini quota exhausted — retry in {QUOTA_COOLDOWN_MINUTES} min") from e
                    if self._is_transient(e) and attempt < 3:
                        delay = 1.0 * (2 ** (attempt - 1))
                        logger.warning(f"[GEMINI] Transient error (attempt {attempt}/3): {e}. Retry in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"[GEMINI] Generation error: {e}")
                        raise RuntimeError(f"Gemini generation failed: {e}") from e
            raise RuntimeError("Gemini failed after 3 retries")

        return await loop.run_in_executor(None, _sync_generate)

    async def generate_structured(self, prompt: str, system_instruction: str) -> dict:
        text = await self.generate(prompt, system_instruction)
        if not text:
            return {}
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            text = json_match.group(1)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"[GEMINI] Failed to parse JSON: {text[:200]}")
            return {}


gemini_provider = GeminiProvider()
