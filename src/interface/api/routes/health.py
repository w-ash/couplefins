from urllib.parse import urlparse

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

from src.config.constants import AppConfig
from src.config.settings import get_settings
from src.infrastructure.persistence.database.db_connection import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    schema_version: str
    schema_current: str
    schema_ok: bool
    database_host: str
    database_mode: str
    chat_available: bool


@router.get("/health")
async def health_check(request: Request) -> HealthResponse:
    settings = get_settings()
    parsed = urlparse(settings.database.url)
    host = parsed.hostname or "unknown"

    if "neon" in host:
        mode = (
            "Neon (pooled)" if settings.database.is_pooled_endpoint else "Neon (direct)"
        )
    else:
        mode = "Local PostgreSQL"

    async with get_session() as session:
        row = await session.execute(text("SELECT version_num FROM alembic_version"))
        schema_current = row.scalar_one_or_none() or "unknown"

    return HealthResponse(
        status="ok",
        version=AppConfig.APP_VERSION,
        schema_version=AppConfig.SCHEMA_VERSION,
        schema_current=schema_current,
        schema_ok=schema_current == AppConfig.SCHEMA_VERSION,
        database_host=host,
        database_mode=mode,
        chat_available=getattr(request.app.state, "anthropic_client", None) is not None,
    )
