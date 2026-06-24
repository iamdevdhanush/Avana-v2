import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.ai_provider_config import AIProviderConfig
from app.models.audit_log import AuditLog
from app.models.user import User
from app.utils.encryption import encrypt_api_key, decrypt_api_key, mask_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai-config", tags=["Admin AI Config"], dependencies=[Depends(require_admin)])


class AIConfigCreate(BaseModel):
    provider: str
    model: str
    api_key: str


class AIConfigResponse(BaseModel):
    id: str
    provider: str
    model: str
    api_key_masked: str
    is_active: bool
    created_at: str
    updated_at: str
    last_tested_at: str | None
    last_test_status: str | None
    last_error: str | None


class TestResult(BaseModel):
    success: bool
    latency_ms: float | None
    error: str | None


class StatusResponse(BaseModel):
    active_config: AIConfigResponse | None
    env_provider: str
    env_model: str
    env_has_key: bool


async def _log_action(
    request: Request,
    db: AsyncSession,
    admin: User,
    action: str,
    resource_id: str | None = None,
    details: dict | None = None,
):
    log = AuditLog(
        id=uuid.uuid4(),
        user_id=admin.id,
        action=action,
        resource_type="ai_provider_config",
        resource_id=resource_id,
        details=details or {},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
        severity="info",
    )
    db.add(log)
    await db.flush()


def _to_response(config: AIProviderConfig) -> AIConfigResponse:
    return AIConfigResponse(
        id=str(config.id),
        provider=config.provider,
        model=config.model,
        api_key_masked=mask_api_key(decrypt_api_key(config.encrypted_api_key)),
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else "",
        updated_at=config.updated_at.isoformat() if config.updated_at else "",
        last_tested_at=config.last_tested_at.isoformat() if config.last_tested_at else None,
        last_test_status=config.last_test_status,
        last_error=config.last_error,
    )


async def _test_provider_connection(provider: str, model: str, api_key: str) -> tuple[bool, float | None, str | None]:
    try:
        start = time.time()
        if provider == "openrouter":
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": [{"role": "user", "content": "Respond with only the word: OK"}], "max_tokens": 10},
                )
                latency = (time.time() - start) * 1000
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if "OK" in content:
                        return True, latency, None
                    return False, latency, f"Unexpected response: {content[:100]}"
                return False, latency, f"HTTP {resp.status_code}: {resp.text[:200]}"
        else:
            return False, None, f"Unknown provider: {provider}"
    except Exception as e:
        return False, None, str(e)


@router.get("")
async def list_configs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(AIProviderConfig).order_by(AIProviderConfig.created_at.desc())
    )
    configs = result.scalars().all()
    return [_to_response(c) for c in configs]


@router.post("", status_code=201)
async def create_config(
    body: AIConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    valid_providers = {"openrouter", "mock"}
    if body.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Invalid provider. Choose from: {valid_providers}")
    if not body.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required")
    if not body.model.strip():
        raise HTTPException(status_code=400, detail="Model name is required")

    encrypted = encrypt_api_key(body.api_key.strip())
    config = AIProviderConfig(
        id=uuid.uuid4(),
        provider=body.provider,
        model=body.model.strip(),
        encrypted_api_key=encrypted,
        is_active=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(config)
    await db.flush()

    await _log_action(request, db, admin, "ai_config_created", str(config.id), {
        "provider": body.provider, "model": body.model,
    })
    await db.commit()
    return _to_response(config)


@router.post("/test")
async def test_config(
    body: AIConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    success, latency, error = await _test_provider_connection(body.provider, body.model, body.api_key)
    return TestResult(success=success, latency_ms=latency, error=error)


@router.post("/activate/{config_id}")
async def activate_config(
    config_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    await db.execute(update(AIProviderConfig).values(is_active=False))
    config.is_active = True
    config.updated_at = datetime.now(timezone.utc)
    await db.flush()

    from app.services.ai.factory import reset_ai_provider
    reset_ai_provider()

    await _log_action(request, db, admin, "ai_config_activated", config_id, {
        "provider": config.provider, "model": config.model,
    })
    await db.commit()
    return _to_response(config)


@router.get("/status")
async def get_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from app.config import settings

    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.is_active == True).limit(1)
    )
    active = result.scalar_one_or_none()

    return StatusResponse(
        active_config=_to_response(active) if active else None,
        env_provider=settings.AI_PROVIDER,
        env_model=settings.OPENROUTER_MODEL,
        env_has_key=bool(settings.OPENROUTER_API_KEY),
    )
