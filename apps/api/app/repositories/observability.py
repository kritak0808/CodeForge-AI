"""
Async repositories for the Observability & Monitoring Platform (Milestone 15).
All extend BaseRepository[T] which uses AsyncSession.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    ObservabilityGeneration,
    AgentMetric,
    WorkflowMetric,
    ApiMetric,
    SystemMetric,
    ErrorEvent,
    AlertRule,
    AlertEvent,
)


class ObservabilityGenerationRepository(BaseRepository[ObservabilityGeneration]):
    def __init__(self, db: AsyncSession):
        super().__init__(ObservabilityGeneration, db)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> List[ObservabilityGeneration]:
        stmt = (
            select(ObservabilityGeneration)
            .where(ObservabilityGeneration.project_id == project_id)
            .order_by(ObservabilityGeneration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_workflow(self, workflow_id: uuid.UUID) -> List[ObservabilityGeneration]:
        stmt = (
            select(ObservabilityGeneration)
            .where(ObservabilityGeneration.workflow_id == workflow_id)
            .order_by(ObservabilityGeneration.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def set_status(
        self, generation_id: uuid.UUID, status: str
    ) -> Optional[ObservabilityGeneration]:
        gen = await self.get(generation_id)
        if gen:
            gen.status = status
            await self.db.flush()
        return gen


class AgentMetricRepository(BaseRepository[AgentMetric]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentMetric, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[AgentMetric]:
        stmt = (
            select(AgentMetric)
            .where(AgentMetric.generation_id == generation_id)
            .order_by(AgentMetric.agent_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_agent(self, agent_name: str) -> List[AgentMetric]:
        stmt = (
            select(AgentMetric)
            .where(AgentMetric.agent_name == agent_name)
            .order_by(AgentMetric.recorded_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class WorkflowMetricRepository(BaseRepository[WorkflowMetric]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowMetric, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[WorkflowMetric]:
        stmt = (
            select(WorkflowMetric)
            .where(WorkflowMetric.generation_id == generation_id)
            .order_by(WorkflowMetric.step_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_workflow(self, workflow_id: uuid.UUID) -> List[WorkflowMetric]:
        stmt = (
            select(WorkflowMetric)
            .where(WorkflowMetric.workflow_id == workflow_id)
            .order_by(WorkflowMetric.recorded_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ApiMetricRepository(BaseRepository[ApiMetric]):
    def __init__(self, db: AsyncSession):
        super().__init__(ApiMetric, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[ApiMetric]:
        stmt = (
            select(ApiMetric)
            .where(ApiMetric.generation_id == generation_id)
            .order_by(ApiMetric.endpoint)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_endpoint(self, endpoint: str) -> List[ApiMetric]:
        stmt = (
            select(ApiMetric)
            .where(ApiMetric.endpoint == endpoint)
            .order_by(ApiMetric.recorded_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SystemMetricRepository(BaseRepository[SystemMetric]):
    def __init__(self, db: AsyncSession):
        super().__init__(SystemMetric, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[SystemMetric]:
        stmt = (
            select(SystemMetric)
            .where(SystemMetric.generation_id == generation_id)
            .order_by(SystemMetric.service_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ErrorEventRepository(BaseRepository[ErrorEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(ErrorEvent, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[ErrorEvent]:
        stmt = (
            select(ErrorEvent)
            .where(ErrorEvent.generation_id == generation_id)
            .order_by(ErrorEvent.occurred_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_severity(
        self, generation_id: uuid.UUID, severity: str
    ) -> List[ErrorEvent]:
        stmt = (
            select(ErrorEvent)
            .where(
                ErrorEvent.generation_id == generation_id,
                ErrorEvent.severity == severity,
            )
            .order_by(ErrorEvent.occurred_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AlertRuleRepository(BaseRepository[AlertRule]):
    def __init__(self, db: AsyncSession):
        super().__init__(AlertRule, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[AlertRule]:
        stmt = (
            select(AlertRule)
            .where(AlertRule.generation_id == generation_id)
            .order_by(AlertRule.rule_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self, generation_id: uuid.UUID) -> List[AlertRule]:
        stmt = (
            select(AlertRule)
            .where(
                AlertRule.generation_id == generation_id,
                AlertRule.is_active == True,  # noqa: E712
            )
            .order_by(AlertRule.rule_name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AlertEventRepository(BaseRepository[AlertEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(AlertEvent, db)

    async def list_by_generation(self, generation_id: uuid.UUID) -> List[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .where(AlertEvent.generation_id == generation_id)
            .order_by(AlertEvent.fired_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_rule(self, rule_id: uuid.UUID) -> List[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .where(AlertEvent.rule_id == rule_id)
            .order_by(AlertEvent.fired_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
