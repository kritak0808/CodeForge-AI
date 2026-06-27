from typing import List, Optional
from uuid import UUID
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ApiKey, UserSession, AuditEvent, FeatureFlag
from app.repositories.base import BaseRepository

class ApiKeyRepository(BaseRepository[ApiKey]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApiKey, db)

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        query = select(self.model).filter(self.model.key_hash == key_hash, self.model.deleted_at == None, self.model.is_active == True)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_user(self, user_id: UUID) -> List[ApiKey]:
        query = select(self.model).filter(self.model.user_id == user_id, self.model.deleted_at == None)
        result = await self.db.execute(query)
        return list(result.scalars().all())

class UserSessionRepository(BaseRepository[UserSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserSession, db)

    async def get_active_by_user(self, user_id: UUID) -> List[UserSession]:
        query = select(self.model).filter(self.model.user_id == user_id, self.model.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

class AuditEventRepository(BaseRepository[AuditEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditEvent, db)

    async def get_by_user(self, user_id: UUID, skip: int = 0, limit: int = 100) -> List[AuditEvent]:
        query = select(self.model).filter(self.model.user_id == user_id).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    def __init__(self, db: AsyncSession):
        super().__init__(FeatureFlag, db)

    async def get_by_name(self, name: str) -> Optional[FeatureFlag]:
        query = select(self.model).filter(self.model.name == name)
        result = await self.db.execute(query)
        return result.scalars().first()
