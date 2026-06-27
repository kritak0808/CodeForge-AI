import hashlib
import secrets
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from app.models import ApiKey, UserSession, AuditEvent, FeatureFlag
from app.repositories.enterprise import ApiKeyRepository, UserSessionRepository, AuditEventRepository, FeatureFlagRepository
from app.schemas.enterprise import ApiKeyCreate, FeatureFlagCreate

class ApiKeyService:
    def __init__(self, repository: ApiKeyRepository):
        self.repository = repository

    @staticmethod
    def _generate_secret() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    async def create_key(self, user_id: UUID, key_in: ApiKeyCreate) -> tuple[ApiKey, str]:
        raw_token = self._generate_secret()
        prefix = raw_token[:8]
        plain_key = f"cf_{prefix}_{raw_token[8:]}"
        key_hash = self._hash_key(plain_key)

        db_key = ApiKey(
            user_id=user_id,
            name=key_in.name,
            key_hash=key_hash,
            prefix=prefix,
            is_active=True,
            expires_at=key_in.expires_at
        )
        created_key = await self.repository.create(db_key)
        return created_key, plain_key

    async def verify_key(self, plain_key: str) -> Optional[ApiKey]:
        key_hash = self._hash_key(plain_key)
        db_key = await self.repository.get_by_hash(key_hash)
        if not db_key:
            return None
        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            return None
        return db_key

    async def list_keys(self, user_id: UUID) -> List[ApiKey]:
        return await self.repository.get_by_user(user_id)

    async def revoke_key(self, key_id: UUID, user_id: UUID) -> Optional[ApiKey]:
        db_key = await self.repository.get(key_id)
        if not db_key or db_key.user_id != user_id:
            return None
        return await self.repository.remove(key_id)

class AuditService:
    def __init__(self, repository: AuditEventRepository):
        self.repository = repository

    async def log_event(
        self,
        action: str,
        resource: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        payload: Optional[dict] = None
    ) -> AuditEvent:
        db_event = AuditEvent(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload
        )
        return await self.repository.create(db_event)

class FeatureFlagService:
    def __init__(self, repository: FeatureFlagRepository):
        self.repository = repository

    async def create_flag(self, flag_in: FeatureFlagCreate) -> FeatureFlag:
        existing = await self.repository.get_by_name(flag_in.name)
        if existing:
            raise ValueError("Feature flag name already exists")
        db_flag = FeatureFlag(
            name=flag_in.name,
            description=flag_in.description,
            is_enabled=flag_in.is_enabled,
            conditions=flag_in.conditions
        )
        return await self.repository.create(db_flag)

    async def is_active(self, flag_name: str, context: Optional[dict] = None) -> bool:
        flag = await self.repository.get_by_name(flag_name)
        if not flag or not flag.is_enabled:
            return False
        
        # Resolve target context rules (e.g. user_id role)
        if flag.conditions and context:
            allowed_roles = flag.conditions.get("roles", [])
            user_role = context.get("role")
            if allowed_roles and user_role not in allowed_roles:
                return False
                
        return True
