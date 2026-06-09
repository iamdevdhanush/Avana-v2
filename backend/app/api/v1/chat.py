from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["AI Chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    try:
        from app.services.gemini import GeminiService
        gemini = GeminiService()

        system_prompt = (
            "You are Avana Safety Assistant, an AI specialized in women's safety in Karnataka, India. "
            "Provide helpful, actionable safety advice based on location context when available. "
            "Be concise, practical, and empathetic. If you don't know something, say so."
        )

        context_parts = []
        if body.history:
            for msg in body.history[-10:]:
                role = msg.get("role", "user")
                text = msg.get("content", "")
                context_parts.append(f"{role}: {text}")

        location_context = ""
        if body.location:
            lat = body.location.get("latitude")
            lng = body.location.get("longitude")
            if lat and lng:
                location_context = f"\nUser's current location: ({lat}, {lng})"

        prompt = f"{location_context}\n\nUser message: {body.message}"

        response_text = gemini.generate(
            prompt,
            system_instruction=system_prompt,
        )

        return ChatResponse(
            response=response_text.strip(),
            recommendations=None,
            risk_context=body.location if body.location else None,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="AI chat service not available. Configure GEMINI_API_KEY.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI chat failed: {str(e)}",
        )


@router.get("/test")
async def test_ai():
    try:
        from app.services.gemini import GeminiService
        gemini = GeminiService()
        response = gemini.generate("Say 'Avana AI is operational' and nothing else.")
        return {
            "status": "ok",
            "response": response.strip(),
            "model": "gemini",
        }
    except ImportError:
        return {
            "status": "unavailable",
            "detail": "Gemini service not configured",
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
        }
