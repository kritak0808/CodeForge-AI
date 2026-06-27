"""
Async repositories for the QA Agent (Milestone 10).

All extend BaseRepository[T] which uses AsyncSession and await.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    QaGeneration,
    QaTestSuite,
    QaTestCase,
    QaTestRun,
    QaBugReport,
    QaCoverageReport,
    QaQualityMetrics,
)


class QaGenerationRepository(BaseRepository[QaGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[QaGeneration]:
        stmt = (
            select(QaGeneration)
            .where(QaGeneration.project_id == project_id)
            .order_by(QaGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[QaGeneration]:
        stmt = (
            select(QaGeneration)
            .where(QaGeneration.workflow_id == workflow_id)
            .order_by(QaGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[QaGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class QaTestSuiteRepository(BaseRepository[QaTestSuite]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaTestSuite, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaTestSuite]:
        stmt = (
            select(QaTestSuite)
            .where(QaTestSuite.generation_id == generation_id)
            .order_by(QaTestSuite.suite_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QaTestCaseRepository(BaseRepository[QaTestCase]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaTestCase, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaTestCase]:
        stmt = (
            select(QaTestCase)
            .where(QaTestCase.generation_id == generation_id)
            .order_by(QaTestCase.case_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QaTestRunRepository(BaseRepository[QaTestRun]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaTestRun, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaTestRun]:
        stmt = (
            select(QaTestRun)
            .where(QaTestRun.generation_id == generation_id)
            .order_by(QaTestRun.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QaBugReportRepository(BaseRepository[QaBugReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaBugReport, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaBugReport]:
        stmt = (
            select(QaBugReport)
            .where(QaBugReport.generation_id == generation_id)
            .order_by(QaBugReport.severity, QaBugReport.title)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QaCoverageReportRepository(BaseRepository[QaCoverageReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaCoverageReport, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaCoverageReport]:
        stmt = (
            select(QaCoverageReport)
            .where(QaCoverageReport.generation_id == generation_id)
            .order_by(QaCoverageReport.coverage_type)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class QaQualityMetricsRepository(BaseRepository[QaQualityMetrics]):
    def __init__(self, db: AsyncSession):
        super().__init__(QaQualityMetrics, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[QaQualityMetrics]:
        stmt = (
            select(QaQualityMetrics)
            .where(QaQualityMetrics.generation_id == generation_id)
            .order_by(QaQualityMetrics.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
