from datetime import timedelta

import pytest
from jose import jwt

from app.config import settings
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    sanitize_input,
)


@pytest.mark.security
def test_password_hashing():
    hashed = hash_password("securepassword123")
    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed != "securepassword123"
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


@pytest.mark.security
def test_password_verification():
    hashed = hash_password("securepassword123")
    assert verify_password("securepassword123", hashed) is True


@pytest.mark.security
def test_password_verification_wrong():
    hashed = hash_password("securepassword123")
    assert verify_password("wrongpassword", hashed) is False


@pytest.mark.security
def test_password_verification_empty():
    hashed = hash_password("securepassword123")
    assert verify_password("", hashed) is False


@pytest.mark.security
def test_create_access_token():
    token = create_access_token({"sub": "user123", "role": "user"})
    assert token is not None
    assert isinstance(token, str)

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "user123"
    assert payload["role"] == "user"
    assert "exp" in payload


@pytest.mark.security
def test_create_access_token_custom_expiry():
    token = create_access_token({"sub": "user123"}, expires_delta=timedelta(hours=1))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "user123"
    assert "exp" in payload


@pytest.mark.security
def test_create_access_token_no_expiry():
    token = create_access_token({"sub": "test_user"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "test_user"


@pytest.mark.security
def test_sanitize_input_removes_html():
    dirty = "<p>Hello World</p>"
    clean = sanitize_input(dirty)
    assert "<p>" not in clean
    assert "Hello World" in clean


@pytest.mark.security
def test_sanitize_input_removes_scripts():
    dirty = "<script>alert('xss')</script>Hello"
    clean = sanitize_input(dirty)
    assert "script" not in clean
    assert "alert" not in clean
    assert "Hello" in clean


@pytest.mark.security
def test_sanitize_input_removes_event_handlers():
    dirty = '<div onclick="alert(1)">Click me</div>'
    clean = sanitize_input(dirty)
    assert "onclick" not in clean.lower()
    assert "Click me" in clean


@pytest.mark.security
def test_sanitize_input_removes_javascript_protocol():
    dirty = '<a href="javascript:void(0)">Link</a>'
    clean = sanitize_input(dirty)
    assert "javascript:" not in clean.lower()
    assert "Link" in clean


@pytest.mark.security
def test_sanitize_input_empty_string():
    assert sanitize_input("") == ""


@pytest.mark.security
def test_sanitize_input_none():
    assert sanitize_input(None) is None


@pytest.mark.security
def test_sanitize_input_no_change():
    clean_text = "Hello, this is a safe message."
    assert sanitize_input(clean_text) == clean_text


@pytest.mark.security
def test_sanitize_input_multiple_tags():
    dirty = "<b>Bold</b> and <i>italic</i> and <u>underline</u>"
    clean = sanitize_input(dirty)
    assert "<b>" not in clean
    assert "<i>" not in clean
    assert "Bold" in clean
    assert "italic" in clean
    assert "underline" in clean


@pytest.mark.security
def test_sanitize_input_nested_scripts():
    dirty = "<div><script>alert(1)</script></div>"
    clean = sanitize_input(dirty)
    assert "script" not in clean


@pytest.mark.security
def test_rate_limiter():
    from app.utils.security import create_rate_limiter
    from unittest.mock import AsyncMock, MagicMock

    limiter = create_rate_limiter()
    assert limiter is not None
    assert callable(limiter)

    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.method = "GET"
    mock_request.url.path = "/test"

    mock_call_next = AsyncMock()
    mock_call_next.return_value = MagicMock(status_code=200)

    import asyncio
    response = asyncio.run(limiter(mock_request, mock_call_next))
    assert response.status_code == 200
    assert mock_call_next.called


@pytest.mark.security
def test_rate_limiter_exceeded():
    from app.utils.security import create_rate_limiter
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings

    original_max = settings.RATE_LIMIT_MAX
    settings.RATE_LIMIT_MAX = 2

    try:
        limiter = create_rate_limiter()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.2"
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        mock_call_next = AsyncMock()
        mock_call_next.return_value = MagicMock(status_code=200)

        import asyncio
        response = asyncio.run(limiter(mock_request, mock_call_next))
        assert response.status_code == 200

        response = asyncio.run(limiter(mock_request, mock_call_next))
        assert response.status_code == 200

        response = asyncio.run(limiter(mock_request, mock_call_next))
        assert response.status_code == 429
        assert "rate limit" in response.body.decode().lower()
    finally:
        settings.RATE_LIMIT_MAX = original_max
