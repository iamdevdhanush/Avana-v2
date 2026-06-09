import google.generativeai as genai
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')

    def is_available(self) -> bool:
        return self.model is not None

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.is_available():
            logger.warning("Gemini API key not configured")
            return ""
        try:
            kwargs = {}
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            response = self.model.generate_content(prompt, **kwargs)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return ""

    def generate_structured(self, prompt: str, system_instruction: str) -> dict:
        import json
        import re
        text = self.generate(prompt, system_instruction)
        if not text:
            return {}
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Gemini JSON response: {text[:200]}")
            return {}

gemini_service = GeminiService()
