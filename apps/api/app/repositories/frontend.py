"""
Async repositories for the Frontend Agent (Milestone 9).

All extend BaseRepository[T] which uses AsyncSession and await.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    FrontendGeneration,
    FrontendPage,
    FrontendComponent,
    FrontendForm,
    FrontendHook,
    FrontendTestReport,
    UiDesignArtifact,
)


class FrontendGenerationRepository(BaseRepository[FrontendGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[FrontendGeneration]:
        stmt = (
            select(FrontendGeneration)
            .where(FrontendGeneration.project_id == project_id)
            .order_by(FrontendGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[FrontendGeneration]:
        stmt = (
            select(FrontendGeneration)
            .where(FrontendGeneration.workflow_id == workflow_id)
            .order_by(FrontendGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[FrontendGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class FrontendPageRepository(BaseRepository[FrontendPage]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendPage, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[FrontendPage]:
        stmt = (
            select(FrontendPage)
            .where(FrontendPage.generation_id == generation_id)
            .order_by(FrontendPage.route_path)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class FrontendComponentRepository(BaseRepository[FrontendComponent]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendComponent, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[FrontendComponent]:
        stmt = (
            select(FrontendComponent)
            .where(FrontendComponent.generation_id == generation_id)
            .order_by(FrontendComponent.component_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class FrontendFormRepository(BaseRepository[FrontendForm]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendForm, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[FrontendForm]:
        stmt = (
            select(FrontendForm)
            .where(FrontendForm.generation_id == generation_id)
            .order_by(FrontendForm.form_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class FrontendHookRepository(BaseRepository[FrontendHook]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendHook, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[FrontendHook]:
        stmt = (
            select(FrontendHook)
            .where(FrontendHook.generation_id == generation_id)
            .order_by(FrontendHook.hook_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class FrontendTestReportRepository(BaseRepository[FrontendTestReport]):
    def __init__(self, db: AsyncSession):
        super().__init__(FrontendTestReport, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID, *, test_type: Optional[str] = None
    ) -> List[FrontendTestReport]:
        stmt = select(FrontendTestReport).where(
            FrontendTestReport.generation_id == generation_id
        )
        if test_type:
            stmt = stmt.where(FrontendTestReport.test_type == test_type)
        stmt = stmt.order_by(FrontendTestReport.test_name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class UiDesignArtifactRepository(BaseRepository[UiDesignArtifact]):
    def __init__(self, db: AsyncSession):
        super().__init__(UiDesignArtifact, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[UiDesignArtifact]:
        stmt = (
            select(UiDesignArtifact)
            .where(UiDesignArtifact.generation_id == generation_id)
            .order_by(UiDesignArtifact.artifact_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
