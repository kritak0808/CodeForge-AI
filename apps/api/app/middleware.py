import time
import uuid
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis
from app.config import settings

# Thread-safe local variable or simple header extraction for correlation IDs
# We will write/propagate headers and response markers
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Retrieve or generate Request ID
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = str(uuid.uuid4())
        
        # 2. Attach Request ID to request state
        request.state.request_id = req_id

        # 3. Process Request
        response: Response = await call_next(request)

        # 4. Attach to response headers
        response.headers["X-Request-ID"] = req_id
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # Apply standard security headers
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

class RedisRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limit: int = 100, window_secs: int = 60):
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_secs = window_secs

    async def dispatch(self, request: Request, call_next):
        # Exclude documentation routes from rate limiting
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/api/v1/health/"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Logins/Registers have a tighter limit (5 per minute)
        limit = 5 if "auth" in request.url.path else self.rate_limit
        
        try:
            r = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1.0,
                socket_timeout=1.0
            )
            now = time.time()
            key = f"rate:{client_ip}:{request.url.path}"
            
            # Sliding window algorithm using Sorted Sets (ZSETS)
            pipe = r.pipeline()
            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, now - self.window_secs)
            pipe.zcard(key)
            pipe.expire(key, self.window_secs)
            results = await pipe.execute()
            
            req_count = results[2]
            await r.close()

            if req_count > limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later."
                        }
                    }
                )
        except Exception:
            # Fallback policy: allow requests to proceed if Redis is offline
            pass

        return await call_next(request)
