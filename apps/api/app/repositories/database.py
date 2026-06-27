"""
Repository layer for the Database Agent (Milestone 7).

All repositories extend BaseRepository (which uses AsyncSession) and
provide design-scoped query methods using await.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    DatabaseDesign,
    DatabaseEntity,
    DatabaseRelationship,
    DatabaseIndex,
    MigrationPlan,
    QueryOptimizationReport,
)


class DatabaseDesignRepository(BaseRepository[DatabaseDesign]):
    def __init__(self, db: AsyncSession):
        super().__init__(DatabaseDesign, db)

    # ── project-scoped listing ─────────────────────────────────────────────

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[DatabaseDesign]:
        stmt = (
            select(DatabaseDesign)
            .where(DatabaseDesign.project_id == project_id)
            .order_by(DatabaseDesign.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── workflow-scoped lookup ─────────────────────────────────────────────

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[DatabaseDesign]:
        stmt = select(DatabaseDesign).where(
            DatabaseDesign.workflow_id == workflow_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # ── status update helper ───────────────────────────────────────────────

    async def set_status(self, design_id: uuid.UUID, status: str) -> Optional[DatabaseDesign]:
        design = await self.get(design_id)
        if design:
            design.status = status
            await self.db.flush()
        return design


class DatabaseEntityRepository(BaseRepository[DatabaseEntity]):
    def __init__(self, db: AsyncSession):
        super().__init__(DatabaseEntity, db)

    async def list_by_design(self, design_id: uuid.UUID) -> List[DatabaseEntity]:
        stmt = (
            select(DatabaseEntity)
            .where(DatabaseEntity.design_id == design_id)
            .order_by(DatabaseEntity.entity_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class DatabaseRelationshipRepository(BaseRepository[DatabaseRelationship]):
    def __init__(self, db: AsyncSession):
        super().__init__(DatabaseRelationship, db)

    async def list_by_design(self, design_id: uuid.UUID) -> List[DatabaseRelationship]:
        stmt = (
            select(DatabaseRelationship)
            .where(DatabaseRelationship.design_id == design_id)
            .order_by(DatabaseRelationship.from_entity)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class DatabaseIndexRepository(BaseRepository[DatabaseIndex]):
    def __init__(self, db: AsyncSession):
        super().__init__(DatabaseIndex, db)

    async def list_by_design(self, design_id: uuid.UUID) -> List[DatabaseIndex]:
        stmt = (
            select(DatabaseIndex)
            .where(DatabaseIndex.design_id == design_id)
            .order_by(DatabaseIndex.table_name, DatabaseIndex.index_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class MigrationPlanRepository(BaseRepository[MigrationPlan]):
    def __init__(self, db: AsyncSession):
        super().__init__(MigrationPlan, db)

    async def get_by_design(self, design_id: uuid.UUID) -> Optional[MigrationPlan]:
        stmt = (
            select(MigrationPlan)
            .where(MigrationPlan.design_id == design_id)
            .order_by(MigrationPlan.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_by_design(self, design_id: uuid.UUID) -> List[MigrationPlan]:
        stmt = (
            select(MigrationPlan)
            .where(MigrationPlan.design_id == design_id)
            .order_by(MigrationPlan.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QueryOptimizationRepository(BaseRepository[QueryOptimizationReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(QueryOptimizationReport, db)

    async def list_by_design(
        self,
        design_id: uuid.UUID,
        *,
        priority: Optional[str] = None,
    ) -> List[QueryOptimizationReport]:
        stmt = select(QueryOptimizationReport).where(
            QueryOptimizationReport.design_id == design_id
        )
        if priority:
            stmt = stmt.where(QueryOptimizationReport.priority == priority)
        stmt = stmt.order_by(
            QueryOptimizationReport.priority,
            QueryOptimizationReport.created_at.desc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
