"""
Async repositories for the Cost Optimization Agent (Milestone 16).
All extend BaseRepository[T] which uses AsyncSession.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    CostGeneration,
    CostReport,
    ResourceUsageMetric,
    OptimizationRecommendation,
    SavingsEstimate,
    BudgetPolicy,
    CostAlert,
)


class CostGenerationRepository(BaseRepository[CostGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(CostGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[CostGeneration]:
        stmt = (
            select(CostGeneration)
            .where(CostGeneration.project_id == project_id)
            .order_by(CostGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_workflow(self, workflow_id: uuid.UUID) -> List[CostGeneration]:
        stmt = (
            select(CostGeneration)
            .where(CostGeneration.workflow_id == workflow_id)
            .order_by(CostGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[CostGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class CostReportRepository(BaseRepository[CostReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(CostReport, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[CostReport]:
        stmt = (
            select(CostReport)
            .where(CostReport.generation_id == generation_id)
            .order_by(CostReport.category)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_category(
        self, generation_id: uuid.UUID, category: str
    ) -> List[CostReport]:
        stmt = (
            select(CostReport)
            .where(
                CostReport.generation_id == generation_id,
                CostReport.category == category,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ResourceUsageMetricRepository(BaseRepository[ResourceUsageMetric]):
    def __init__(self, db: AsyncSession):
        super().__init__(ResourceUsageMetric, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[ResourceUsageMetric]:
        stmt = (
            select(ResourceUsageMetric)
            .where(ResourceUsageMetric.generation_id == generation_id)
            .order_by(ResourceUsageMetric.resource_type)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_resource_type(
        self, generation_id: uuid.UUID, resource_type: str
    ) -> List[ResourceUsageMetric]:
        stmt = (
            select(ResourceUsageMetric)
            .where(
                ResourceUsageMetric.generation_id == generation_id,
                ResourceUsageMetric.resource_type == resource_type,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class OptimizationRecommendationRepository(BaseRepository[OptimizationRecommendation]):
    def __init__(self, db: AsyncSession):
        super().__init__(OptimizationRecommendation, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[OptimizationRecommendation]:
        stmt = (
            select(OptimizationRecommendation)
            .where(OptimizationRecommendation.generation_id == generation_id)
            .order_by(OptimizationRecommendation.estimated_savings.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_impact_level(
        self, generation_id: uuid.UUID, impact_level: str
    ) -> List[OptimizationRecommendation]:
        stmt = (
            select(OptimizationRecommendation)
            .where(
                OptimizationRecommendation.generation_id == generation_id,
                OptimizationRecommendation.impact_level == impact_level,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SavingsEstimateRepository(BaseRepository[SavingsEstimate]):
    def __init__(self, db: AsyncSession):
        super().__init__(SavingsEstimate, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[SavingsEstimate]:
        stmt = (
            select(SavingsEstimate)
            .where(SavingsEstimate.generation_id == generation_id)
            .order_by(SavingsEstimate.monthly_savings.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class BudgetPolicyRepository(BaseRepository[BudgetPolicy]):
    def __init__(self, db: AsyncSession):
        super().__init__(BudgetPolicy, db)

    async def get_by_project(self, project_id: uuid.UUID) -> Optional[BudgetPolicy]:
        stmt = (
            select(BudgetPolicy)
            .where(
                BudgetPolicy.project_id == project_id,
                BudgetPolicy.is_active == True,  # noqa: E712
            )
            .order_by(BudgetPolicy.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_active(self) -> List[BudgetPolicy]:
        stmt = (
            select(BudgetPolicy)
            .where(BudgetPolicy.is_active == True)  # noqa: E712
            .order_by(BudgetPolicy.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class CostAlertRepository(BaseRepository[CostAlert]):
    def __init__(self, db: AsyncSession):
        super().__init__(CostAlert, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[CostAlert]:
        stmt = (
            select(CostAlert)
            .where(CostAlert.generation_id == generation_id)
            .order_by(CostAlert.fired_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_open_alerts(self, generation_id: uuid.UUID) -> List[CostAlert]:
        stmt = (
            select(CostAlert)
            .where(
                CostAlert.generation_id == generation_id,
                CostAlert.status == "OPEN",
            )
            .order_by(CostAlert.fired_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
