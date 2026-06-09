from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_no_api_key(async_client: AsyncClient, auth_headers):
    payload = {"message": "What are some safety tips for Bengaluru?"}
    with patch("app.api.v1.chat.GeminiService") as MockGemini:
        instance = MockGemini.return_value
        instance.is_available.return_value = False
        response = await async_client.post("/api/v1/chat/message", json=payload, headers=auth_headers)
        assert response.status_code == 501
        data = response.json()
        assert "not available" in data["detail"].lower() or "configure" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_empty_message(async_client: AsyncClient, auth_headers):
    payload = {"message": ""}
    response = await async_client.post("/api/v1/chat/message", json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_test(async_client: AsyncClient):
    response = await async_client.get("/api/v1/chat/test")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "unavailable", "error")


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_with_history(async_client: AsyncClient, auth_headers):
    payload = {
        "message": "What should I do if I feel unsafe?",
        "history": [
            {"role": "user", "content": "Is Koramangala safe at night?"},
            {"role": "assistant", "content": "Koramangala has moderate safety ratings. Stay on main roads."},
        ],
        "location": {"latitude": 12.9352, "longitude": 77.6245},
    }
    with patch("app.api.v1.chat.GeminiService") as MockGemini:
        instance = MockGemini.return_value
        instance.is_available.return_value = True
        instance.generate.return_value = "Stay aware of your surroundings and use well-lit streets."
        response = await async_client.post("/api/v1/chat/message", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "Stay aware of your surroundings and use well-lit streets."
        assert "recommendations" in data
        assert "risk_context" in data


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_without_auth(async_client: AsyncClient):
    payload = {"message": "Is it safe to travel alone?"}
    response = await async_client.post("/api/v1/chat/message", json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.chat
async def test_chat_gemini_error(async_client: AsyncClient, auth_headers):
    payload = {"message": "Tell me about safety in Bangalore."}
    with patch("app.api.v1.chat.GeminiService") as MockGemini:
        instance = MockGemini.return_value
        instance.is_available.return_value = True
        instance.generate.side_effect = Exception("API Error")
        response = await async_client.post("/api/v1/chat/message", json=payload, headers=auth_headers)
        assert response.status_code == 500
        data = response.json()
        assert "API Error" in data["detail"] or "failed" in data["detail"].lower()
