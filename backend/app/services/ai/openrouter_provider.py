import json
import logging
import time
from typing import Optional

import httpx

from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(AIProvider):
    name = "openrouter"

    @property
    def model_name(self) -> str:
        return self.model

    def __init__(self, api_key: str | None = None, model: str | None = None):
        from app.config import settings
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.OPENROUTER_MODEL or "openai/gpt-4o-mini"
        self._available = False
        self._init_error = None
        self._quota_until = None
        self._init()

    def _init(self):
        if not self.api_key:
            self._init_error = "OPENROUTER_API_KEY not configured"
            logger.warning(f"[OPENROUTER] {self._init_error}")
            return
        if len(self.api_key) < 10:
            self._init_error = f"OPENROUTER_API_KEY too short (len={len(self.api_key)})"
            logger.error(f"[OPENROUTER] {self._init_error}")
            return
        self._available = True
        logger.info(f"[OPENROUTER] Initialized -- model={self.model}")

    def is_available(self) -> bool:
        if self._quota_until and time.time() < self._quota_until:
            return False
        return self._available

    def get_status(self) -> dict:
        status = {
            "provider": "openrouter",
            "model": self.model,
            "has_api_key": bool(self.api_key),
        }
        if self._quota_until and time.time() < self._quota_until:
            remaining = int(self._quota_until - time.time())
            status["available"] = False
            status["status"] = "QUOTA_EXCEEDED"
            status["error"] = "OpenRouter quota exceeded"
            status["retry_after_seconds"] = remaining
        elif not self._available:
            status["available"] = False
            status["status"] = "OFFLINE"
            status["error"] = self._init_error or "OpenRouter unavailable"
        else:
            status["available"] = True
            status["status"] = "ONLINE"
            status["error"] = None
        return status

    async def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        from app.utils.timing import Timer

        with Timer("7. OpenRouter request"):
            if not self._available:
                logger.warning(f"[OPENROUTER] Unavailable: {self._init_error}")
                return ""
            if self._quota_until and time.time() < self._quota_until:
                remaining = int(self._quota_until - time.time())
                logger.warning(f"[OPENROUTER] Quota cooldown -- {remaining}s remaining")
                raise RuntimeError(f"OpenRouter quota cooldown -- retry in {remaining}s")

            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            for attempt in range(1, 4):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            f"{OPENROUTER_BASE_URL}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "https://avana.app",
                                "X-Title": "Avana Safety Intelligence",
                            },
                            json={
                                "model": self.model,
                                "messages": messages,
                                "max_tokens": 4096,
                            },
                        )
                        if resp.status_code == 429:
                            logger.warning(f"[OPENROUTER] Rate limited (attempt {attempt}/3)")
                            if attempt < 3:
                                import asyncio
                                await asyncio.sleep(2.0 * attempt)
                                continue
                            self._quota_until = time.time() + 300
                            raise RuntimeError("OpenRouter rate limited")
                        resp.raise_for_status()
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        logger.info(f"[OPENROUTER] Response ({len(content)} chars)")
                        return content
                except httpx.TimeoutException:
                    if attempt < 3:
                        import asyncio
                        await asyncio.sleep(1.0 * attempt)
                        continue
                    logger.error("[OPENROUTER] Timeout after 3 attempts")
                    return ""
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (502, 503) and attempt < 3:
                        import asyncio
                        await asyncio.sleep(2.0 * attempt)
                        continue
                    logger.error(f"[OPENROUTER] HTTP {e.response.status_code}: {e.response.text[:200]}")
                    return ""
                except Exception as e:
                    logger.error(f"[OPENROUTER] Error: {e}")
                    if attempt < 3:
                        import asyncio
                        await asyncio.sleep(1.0)
                        continue
                    return ""

            return ""
