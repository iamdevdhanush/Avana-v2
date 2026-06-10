from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: Optional[List[dict]] = None
    location: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    recommendations: Optional[List[str]] = None
    risk_context: Optional[dict] = None
