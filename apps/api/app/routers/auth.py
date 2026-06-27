import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
import redis.asyncio as aioredis
from app.config import settings
from app.dependencies import get_user_service, get_user_repository
from app.services.user import UserService
from app.schemas.user import UserCreate, UserOut, UserLogin
from app.schemas.token import Token
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["authentication"])

class VerificationRequest(BaseModel):
    token: str

class ResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    access_token: str
    refresh_token: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, user_service: UserService = Depends(get_user_service)):
    try:
        user = await user_service.register_user(user_in)
        return {
            "success": True,
            "data": UserOut.model_validate(user),
            "error": None
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login")
async def login(login_in: UserLogin, user_service: UserService = Depends(get_user_service)):
    user = await user_service.authenticate_user(login_in)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, refresh_token = user_service.generate_tokens(user)
    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        },
        "error": None
    }

@router.post("/verify-email")
async def verify_email(req: VerificationRequest, user_service: UserService = Depends(get_user_service)):
    success = await user_service.verify_email(req.token)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")
    return {"success": True, "data": {"message": "Email verified successfully"}, "error": None}

@router.post("/request-reset")
async def request_reset(req: ResetRequest, user_service: UserService = Depends(get_user_service)):
    token = await user_service.request_password_reset(req.email)
    # Return verification reset token mock
    return {"success": True, "data": {"reset_token": token, "message": "Password reset token generated"}, "error": None}

@router.post("/reset-password")
async def reset_password(req: PasswordResetConfirm, user_service: UserService = Depends(get_user_service)):
    success = await user_service.reset_password(req.token, req.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return {"success": True, "data": {"message": "Password reset successfully"}, "error": None}

@router.post("/refresh")
async def refresh_tokens(req: RefreshRequest, user_service: UserService = Depends(get_user_service)):
    # 1. Decode token
    try:
        payload = jwt.decode(req.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        
        jti = payload.get("jti")
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # 2. Skip Redis checks if disabled
    if not settings.REDIS_DISABLED:
        # 2. Check if jti is blacklisted in Redis (RTR violation check)
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
        try:
            is_revoked = await r.get(f"blacklist:{jti}")
            if is_revoked:
                # Replay Attack detected: invalidate all sessions for this user
                await r.set(f"user_revoked:{username}", "true", ex=86400)
                await r.close()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token compromised and revoked")

            # 3. Add current refresh token to blacklist (since we are rotating it)
            await r.set(f"blacklist:{jti}", "true", ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

            # 4. Generate new tokens
            user = await user_service.repository.get_by_username(username)
            if not user:
                await r.close()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

            # Check if user sessions are revoked globally
            is_revoked_globally = await r.get(f"user_revoked:{username}")
            if is_revoked_globally:
                await r.close()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User sessions revoked")

            access_token, new_refresh_token = user_service.generate_tokens(user)
            await r.close()
        except Exception as e:
            # If Redis fails, log but continue with token generation
            await r.close()
            user = await user_service.repository.get_by_username(username)
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            access_token, new_refresh_token = user_service.generate_tokens(user)
    else:
        # Redis disabled - simple token refresh
        user = await user_service.repository.get_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        access_token, new_refresh_token = user_service.generate_tokens(user)

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        },
        "error": None
    }

@router.post("/logout")
async def logout(req: LogoutRequest):
    # Retrieve jti from refresh token and blacklist it
    if not settings.REDIS_DISABLED:
        try:
            refresh_payload = jwt.decode(req.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            jti = refresh_payload.get("jti")
            
            r = aioredis.from_url(settings.REDIS_URL, socket_timeout=1.0)
            # Blacklist refresh token
            if jti:
                await r.set(f"blacklist:{jti}", "true", ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
            
            # Blacklist access token (using token signature hash or expiry)
            access_payload = jwt.decode(req.access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            exp = access_payload.get("exp")
            now = datetime.datetime.utcnow().timestamp()
            ttl = int(exp - now) if exp and exp > now else 3600
            
            await r.set(f"blacklist:{req.access_token[-30:]}", "true", ex=ttl)
            await r.close()
        except Exception:
            pass
    
    return {"success": True, "data": {"message": "Logged out successfully"}, "error": None}
