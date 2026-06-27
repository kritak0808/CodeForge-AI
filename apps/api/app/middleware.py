import time
import uuid

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import redis.asyncio as aioredis

from app.config import settings


# -----------------------------------------------------------------------------
# Request ID Middleware
# -----------------------------------------------------------------------------
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID")

        if not req_id:
            req_id = str(uuid.uuid4())

        request.state.request_id = req_id

        response: Response = await call_next(request)

        response.headers["X-Request-ID"] = req_id

        return response


# -----------------------------------------------------------------------------
# Security Headers Middleware
# -----------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Standard security headers
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # ------------------------------------------------------------------
        # Swagger UI needs external JS/CSS.
        # Keep CSP relaxed ONLY for documentation pages.
        # ------------------------------------------------------------------
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:

            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

        else:
            # Strict policy for API endpoints
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "frame-ancestors 'none';"
            )

        return response


# -----------------------------------------------------------------------------
# Redis Rate Limiter
# -----------------------------------------------------------------------------
class RedisRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit: int = 100, window_secs: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_secs = window_secs

    async def dispatch(self, request: Request, call_next):

        # Skip docs and health endpoints
        if request.url.path in [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/health/",
        ]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Login/Register gets stricter rate limit
        limit = 5 if "/auth/" in request.url.path else self.rate_limit

        try:
            redis = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )

            now = time.time()

            key = f"rate:{client_ip}:{request.url.path}"

            pipe = redis.pipeline()

            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, now - self.window_secs)
            pipe.zcard(key)
            pipe.expire(key, self.window_secs)

            results = await pipe.execute()

            request_count = results[2]

            await redis.close()

            if request_count > limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                        },
                    },
                )

        except Exception:
            # Allow traffic if Redis is unavailable
            pass

        return await call_next(request)