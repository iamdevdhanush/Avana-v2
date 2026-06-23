import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    name: str = "unknown"

    @property
    def model_name(self) -> str:
        return "unknown"

    @abstractmethod
    async def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate text response from the AI model."""
        ...

    async def generate_structured(self, prompt: str, system_instruction: str) -> dict:
        """Generate a structured JSON response from the AI model.
        
        Default implementation calls generate() and parses JSON.
        Providers may override for native structured output.
        """
        import json, re
        text = await self.generate(prompt, system_instruction)
        if not text:
            return {}
        cleaned = text.strip()
        for prefix in ("```json", "```"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        try:
            return json.loads(cleaned.strip())
        except (json.JSONDecodeError, ValueError):
            logger.error(f"Failed to parse AI JSON response from {self.name}: {cleaned[:200]}")
            return {}

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available for use."""
        ...

    @abstractmethod
    def get_status(self) -> dict:
        """Get detailed status information about the provider."""
        ...
