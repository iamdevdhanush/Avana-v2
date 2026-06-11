import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiQuotaExceeded(Exception):
    pass


class GeminiAuthError(Exception):
    pass


class GeminiTransientError(Exception):
    pass


class GeminiService:
    def __init__(self):
        self.api_key = None
        self.model = None
        self._last_call_time = 0
        self._call_count_this_minute = 0
        self._minute_start = time.time()
        self._available = False
        self._init_error = None
        self._init()

    def _init(self):
        from app.config import settings
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            self._available = False
            self._init_error = "GEMINI_API_KEY not configured"
            logger.warning(self._init_error)
            return
        if not api_key.startswith("AIza"):
            self._available = False
            self._init_error = "GEMINI_API_KEY does not appear valid (should start with AIza)"
            logger.error(self._init_error)
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.api_key = api_key
            self._available = True
            logger.info("Gemini service initialized successfully")
        except Exception as e:
            self._available = False
            self._init_error = f"Gemini init failed: {e}"
            logger.error(self._init_error)

    def is_available(self) -> bool:
        return self._available

    def get_status(self) -> dict:
        return {
            "available": self._available,
            "error": self._init_error,
            "model": "gemini-2.0-flash" if self._available else None,
        }

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
        return any(k in err_str for k in ["429", "503", "timeout", "rate", "quota", "internal", "unavailable", "deadline"])

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self._available:
            logger.warning(f"Gemini unavailable: {self._init_error}")
            return ""
        last_exc = None
        for attempt in range(1, 4):
            try:
                self._check_rate_limit()
                kwargs = {}
                if system_instruction:
                    kwargs["system_instruction"] = system_instruction
                response = self.model.generate_content(prompt, **kwargs)
                if not response or not response.text:
                    logger.warning("Gemini returned empty response")
                    return ""
                logger.info(f"Gemini response received ({len(response.text)} chars)")
                return response.text
            except GeminiQuotaExceeded as e:
                logger.warning(str(e))
                return ""
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "API_KEY_INVALID" in err_str or "API key" in err_str:
                    self._available = False
                    self._init_error = "Gemini API key invalid or rejected"
                    logger.error(self._init_error)
                    return ""
                if self._is_transient(e) and attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Gemini transient error (attempt {attempt}/3): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Gemini generation error: {e}")
                    return ""
        logger.error(f"Gemini failed after 3 attempts: {last_exc}")
        return ""

    def generate_structured(self, prompt: str, system_instruction: str) -> dict:
        text = self.generate(prompt, system_instruction)
        if not text:
            return {}
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            text = json_match.group(1)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Gemini JSON response: {text[:300]}")
            return {}


gemini_service = GeminiService()
