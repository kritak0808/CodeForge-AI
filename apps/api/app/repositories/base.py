from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: UUID) -> Optional[ModelType]:
        # Reflect primary key attribute name dynamically
        pk_name = self.model.__mapper__.primary_key[0].name
        pk_col = getattr(self.model, pk_name)
        
        filters = [pk_col == id]
        if hasattr(self.model, "deleted_at"):
            filters.append(self.model.deleted_at == None)
            
        query = select(self.model).filter(*filters)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_multi(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        query = select(self.model)
        if hasattr(self.model, "deleted_at"):
            query = query.filter(self.model.deleted_at == None)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list(self) -> List[ModelType]:
        query = select(self.model)
        if hasattr(self.model, "deleted_at"):
            query = query.filter(self.model.deleted_at == None)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, obj_in: Any) -> ModelType:
        self.db.add(obj_in)
        await self.db.commit()
        await self.db.refresh(obj_in)
        return obj_in

    async def update(self, db_obj: ModelType, obj_in: Any) -> ModelType:
        for field, value in obj_in.items() if isinstance(obj_in, dict) else obj_in.__dict__.items():
            if hasattr(db_obj, field) and value is not None:
                setattr(db_obj, field, value)
        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.utcnow()
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def remove(self, id: UUID) -> Optional[ModelType]:
        obj = await self.get(id)
        if obj:
            if hasattr(self.model, "deleted_at"):
                obj.deleted_at = datetime.utcnow()
                self.db.add(obj)
            else:
                await self.db.delete(obj)
            await self.db.commit()
            if hasattr(self.model, "deleted_at"):
                await self.db.refresh(obj)
        return obj
