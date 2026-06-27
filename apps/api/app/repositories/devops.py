"""
Async repositories for the DevOps Agent (Milestone 12).

All extend BaseRepository[T] which uses AsyncSession.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    DevopsGeneration,
    DockerArtifact,
    KubernetesArtifact,
    HelmArtifact,
    TerraformArtifact,
    CicdPipeline,
    DeploymentTemplate,
)


class DevopsGenerationRepository(BaseRepository[DevopsGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(DevopsGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[DevopsGeneration]:
        stmt = (
            select(DevopsGeneration)
            .where(DevopsGeneration.project_id == project_id)
            .order_by(DevopsGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[DevopsGeneration]:
        stmt = (
            select(DevopsGeneration)
            .where(DevopsGeneration.workflow_id == workflow_id)
            .order_by(DevopsGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[DevopsGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class DockerArtifactRepository(BaseRepository[DockerArtifact]):
    def __init__(self, db: AsyncSession):
        super().__init__(DockerArtifact, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[DockerArtifact]:
        stmt = (
            select(DockerArtifact)
            .where(DockerArtifact.generation_id == generation_id)
            .order_by(DockerArtifact.file_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class KubernetesArtifactRepository(BaseRepository[KubernetesArtifact]):
    def __init__(self, db: AsyncSession):
        super().__init__(KubernetesArtifact, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[KubernetesArtifact]:
        stmt = (
            select(KubernetesArtifact)
            .where(KubernetesArtifact.generation_id == generation_id)
            .order_by(KubernetesArtifact.manifest_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class HelmArtifactRepository(BaseRepository[HelmArtifact]):
    def __init__(self, db: AsyncSession):
        super().__init__(HelmArtifact, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[HelmArtifact]:
        stmt = (
            select(HelmArtifact)
            .where(HelmArtifact.generation_id == generation_id)
            .order_by(HelmArtifact.file_path)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TerraformArtifactRepository(BaseRepository[TerraformArtifact]):
    def __init__(self, db: AsyncSession):
        super().__init__(TerraformArtifact, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[TerraformArtifact]:
        stmt = (
            select(TerraformArtifact)
            .where(TerraformArtifact.generation_id == generation_id)
            .order_by(TerraformArtifact.file_path)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class CicdPipelineRepository(BaseRepository[CicdPipeline]):
    def __init__(self, db: AsyncSession):
        super().__init__(CicdPipeline, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[CicdPipeline]:
        stmt = (
            select(CicdPipeline)
            .where(CicdPipeline.generation_id == generation_id)
            .order_by(CicdPipeline.provider)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class DeploymentTemplateRepository(BaseRepository[DeploymentTemplate]):
    def __init__(self, db: AsyncSession):
        super().__init__(DeploymentTemplate, db)

    async def list_by_generation(
        self, generation_id: uuid.UUID
    ) -> List[DeploymentTemplate]:
        stmt = (
            select(DeploymentTemplate)
            .where(DeploymentTemplate.generation_id == generation_id)
            .order_by(DeploymentTemplate.target_platform)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
