from fastapi import APIRouter
from sqlalchemy import text

from app.api.v1.deps import SessionDep
from app.core.redis import get_redis
from app.schemas.common import HealthStatus, MetricsStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthStatus)
async def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
async def ready(session: SessionDep) -> HealthStatus:
    await session.execute(text("select 1"))
    redis = get_redis()
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    return HealthStatus(status="ready")


@router.get("/metrics", response_model=MetricsStatus)
async def metrics(session: SessionDep) -> MetricsStatus:
    await session.execute(text("select 1"))
    redis = get_redis()
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    return MetricsStatus(service="voltscope-api", status="ok", database="ok", redis="ok")
