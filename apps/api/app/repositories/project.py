from typing import List
from uuid import UUID
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Project
from app.repositories.base import BaseRepository

class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(Project, db)

    async def get_by_owner(self, user_id: UUID, skip: int = 0, limit: int = 100) -> List[Project]:
        query = select(self.model).filter(self.model.user_id == user_id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
