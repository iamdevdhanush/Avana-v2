from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None
    location: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    recommendations: Optional[List[str]] = None
    risk_context: Optional[dict] = None
