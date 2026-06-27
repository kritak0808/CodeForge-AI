"""
Async repositories for the Security Agent (Milestone 11).

All extend BaseRepository[T] which uses AsyncSession.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    SecurityGeneration,
    ThreatModel,
    SecurityFinding,
    DependencyScan,
    SecretScan,
    RbacAudit,
    SecurityReport,
)


class SecurityGenerationRepository(BaseRepository[SecurityGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(SecurityGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[SecurityGeneration]:
        stmt = (
            select(SecurityGeneration)
            .where(SecurityGeneration.project_id == project_id)
            .order_by(SecurityGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[SecurityGeneration]:
        stmt = (
            select(SecurityGeneration)
            .where(SecurityGeneration.workflow_id == workflow_id)
            .order_by(SecurityGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[SecurityGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class ThreatModelRepository(BaseRepository[ThreatModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(ThreatModel, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[ThreatModel]:
        stmt = (
            select(ThreatModel)
            .where(ThreatModel.generation_id == generation_id)
            .order_by(ThreatModel.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SecurityFindingRepository(BaseRepository[SecurityFinding]):
    def __init__(self, db: AsyncSession):
        super().__init__(SecurityFinding, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[SecurityFinding]:
        stmt = (
            select(SecurityFinding)
            .where(SecurityFinding.generation_id == generation_id)
            .order_by(SecurityFinding.severity, SecurityFinding.title)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class DependencyScanRepository(BaseRepository[DependencyScan]):
    def __init__(self, db: AsyncSession):
        super().__init__(DependencyScan, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[DependencyScan]:
        stmt = (
            select(DependencyScan)
            .where(DependencyScan.generation_id == generation_id)
            .order_by(DependencyScan.package_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SecretScanRepository(BaseRepository[SecretScan]):
    def __init__(self, db: AsyncSession):
        super().__init__(SecretScan, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[SecretScan]:
        stmt = (
            select(SecretScan)
            .where(SecretScan.generation_id == generation_id)
            .order_by(SecretScan.file_path, SecretScan.line_number)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class RbacAuditRepository(BaseRepository[RbacAudit]):
    def __init__(self, db: AsyncSession):
        super().__init__(RbacAudit, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[RbacAudit]:
        stmt = (
            select(RbacAudit)
            .where(RbacAudit.generation_id == generation_id)
            .order_by(RbacAudit.role_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SecurityReportRepository(BaseRepository[SecurityReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(SecurityReport, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[SecurityReport]:
        stmt = (
            select(SecurityReport)
            .where(SecurityReport.generation_id == generation_id)
            .order_by(SecurityReport.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
