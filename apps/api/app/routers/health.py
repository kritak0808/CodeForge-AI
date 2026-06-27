import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/health", tags=["health"])

@router.get("", status_code=status.HTTP_200_OK)
async def check_health(db: AsyncSession = Depends(get_db)):
    db_status = "unhealthy"
    redis_status = "disabled" if settings.REDIS_DISABLED else "unhealthy"
    kafka_status = "disabled" if settings.KAFKA_DISABLED else "unhealthy"

    # 1. Database check
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        pass

    # 2. Redis check (skip if disabled)
    if not settings.REDIS_DISABLED:
        try:
            r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
            if await r.ping():
                redis_status = "healthy"
            await r.close()
        except Exception:
            redis_status = "unavailable"

    # 3. Kafka: mark healthy when disabled for local dev
    if settings.KAFKA_DISABLED:
        kafka_status = "disabled"

    # Overall health: ok if DB is healthy (Redis/Kafka optional)
    overall = "ok" if db_status == "healthy" else "degraded"

    return {
        "success": True,
        "data": {
            "status": overall,
            "version": "1.0.0",
            "env": settings.ENV,
            "database": db_status,
            "redis": redis_status,
            "kafka": kafka_status,
        },
        "error": None,
    }
