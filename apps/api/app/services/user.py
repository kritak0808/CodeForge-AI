import datetime
import uuid
from typing import Optional, Tuple
from jose import jwt, JWTError
import redis.asyncio as aioredis
from app.config import settings
from app.models import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserLogin
from app.schemas.token import Token
from app.security import get_password_hash, verify_password

class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def register_user(self, user_in: UserCreate) -> User:
        existing_user = await self.repository.get_by_username(user_in.username)
        if existing_user:
            raise ValueError("Username already registered")
        existing_email = await self.repository.get_by_email(user_in.email)
        if existing_email:
            raise ValueError("Email already registered")

        hashed_pass = get_password_hash(user_in.password)
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            password_hash=hashed_pass,
            role=user_in.role,
            is_verified=False,
            # Generate a mock email verification token
            verification_token=str(uuid.uuid4())
        )
        return await self.repository.create(db_user)

    async def authenticate_user(self, login_in: UserLogin) -> Optional[User]:
        db_user = await self.repository.get_by_username(login_in.username)
        if not db_user or db_user.deleted_at is not None:
            return None
        if not verify_password(login_in.password, db_user.password_hash):
            return None
        return db_user

    def generate_tokens(self, user: User) -> Tuple[str, str]:
        # Access Token
        access_expires = datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_exp = datetime.datetime.utcnow() + access_expires
        access_payload = {
            "sub": user.username,
            "role": user.role,
            "user_id": str(user.user_id),
            "type": "access",
            "exp": access_exp
        }
        access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        # Refresh Token
        refresh_expires = datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_exp = datetime.datetime.utcnow() + refresh_expires
        refresh_payload = {
            "sub": user.username,
            "role": user.role,
            "user_id": str(user.user_id),
            "type": "refresh",
            "jti": str(uuid.uuid4()),  # unique token identifier
            "exp": refresh_exp
        }
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return access_token, refresh_token

    async def verify_email(self, token: str) -> bool:
        from sqlalchemy import select
        query = await self.repository.db.execute(
            select(self.repository.model).where(self.repository.model.verification_token == token)
        )
        user = query.scalars().first()
        if user:
            user.is_verified = True
            user.verification_token = None
            await self.repository.db.commit()
            return True
        return False

    async def request_password_reset(self, email: str) -> Optional[str]:
        user = await self.repository.get_by_email(email)
        if not user:
            return None
        token = str(uuid.uuid4())
        user.reset_token = token
        await self.repository.db.commit()
        return token

    async def reset_password(self, token: str, new_password: str) -> bool:
        from sqlalchemy import select
        query = await self.repository.db.execute(
            select(self.repository.model).where(self.repository.model.reset_token == token)
        )
        user = query.scalars().first()
        if user:
            user.password_hash = get_password_hash(new_password)
            user.reset_token = None
            await self.repository.db.commit()
            return True
        return False
