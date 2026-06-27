"""
Async repositories for the Backend Agent (Milestone 8).

All extend BaseRepository[T] which uses AsyncSession and await.
Each provides generation-scoped query helpers consumed by BackendGenerationService.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    BackendGeneration,
    ApiEndpoint,
    ServiceDefinition,
    RepositoryDefinition,
    BusinessRule,
    ApiTestReport,
)


class BackendGenerationRepository(BaseRepository[BackendGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(BackendGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[BackendGeneration]:
        stmt = (
            select(BackendGeneration)
            .where(BackendGeneration.project_id == project_id)
            .order_by(BackendGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[BackendGeneration]:
        stmt = (
            select(BackendGeneration)
            .where(BackendGeneration.workflow_id == workflow_id)
            .order_by(BackendGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[BackendGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class ApiEndpointRepository(BaseRepository[ApiEndpoint]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApiEndpoint, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[ApiEndpoint]:
        stmt = (
            select(ApiEndpoint)
            .where(ApiEndpoint.generation_id == generation_id)
            .order_by(ApiEndpoint.path, ApiEndpoint.method)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ServiceDefinitionRepository(BaseRepository[ServiceDefinition]):
    def __init__(self, db: AsyncSession):
        super().__init__(ServiceDefinition, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[ServiceDefinition]:
        stmt = (
            select(ServiceDefinition)
            .where(ServiceDefinition.generation_id == generation_id)
            .order_by(ServiceDefinition.service_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class RepositoryDefinitionRepository(BaseRepository[RepositoryDefinition]):
    def __init__(self, db: AsyncSession):
        super().__init__(RepositoryDefinition, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[RepositoryDefinition]:
        stmt = (
            select(RepositoryDefinition)
            .where(RepositoryDefinition.generation_id == generation_id)
            .order_by(RepositoryDefinition.repo_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class BusinessRuleRepository(BaseRepository[BusinessRule]):
    def __init__(self, db: AsyncSession):
        super().__init__(BusinessRule, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID, *, rule_type: Optional[str] = None
    ) -> List[BusinessRule]:
        stmt = select(BusinessRule).where(
            BusinessRule.generation_id == generation_id
        )
        if rule_type:
            stmt = stmt.where(BusinessRule.rule_type == rule_type)
        stmt = stmt.order_by(BusinessRule.rule_name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ApiTestReportRepository(BaseRepository[ApiTestReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApiTestReport, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID, *, test_type: Optional[str] = None
    ) -> List[ApiTestReport]:
        stmt = select(ApiTestReport).where(
            ApiTestReport.generation_id == generation_id
        )
        if test_type:
            stmt = stmt.where(ApiTestReport.test_type == test_type)
        stmt = stmt.order_by(ApiTestReport.test_name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
