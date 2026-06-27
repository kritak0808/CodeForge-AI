"""
Async repositories for the Autonomous SDLC Controller Agent (Milestone 17).
All repositories extend BaseRepository[T] using SQLAlchemy AsyncSession.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models import (
    AutonomousController,
    WorkflowDecision,
    AgentHealth,
    RetryHistory,
    FailureEvent,
    RollbackEvent,
    ExecutionPlan,
    ControllerLog,
)


class AutonomousControllerRepository(BaseRepository[AutonomousController]):
    def __init__(self, db: AsyncSession):
        super().__init__(AutonomousController, db)

    async def get_by_workflow(self, workflow_id: uuid.UUID) -> Optional[AutonomousController]:
        stmt = (
            select(AutonomousController)
            .where(AutonomousController.workflow_id == workflow_id)
            .order_by(AutonomousController.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_by_project(self, project_id: uuid.UUID) -> List[AutonomousController]:
        stmt = (
            select(AutonomousController)
            .where(AutonomousController.project_id == project_id)
            .order_by(AutonomousController.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class WorkflowDecisionRepository(BaseRepository[WorkflowDecision]):
    def __init__(self, db: AsyncSession):
        super().__init__(WorkflowDecision, db)

    async def list_by_controller(self, controller_id: uuid.UUID) -> List[WorkflowDecision]:
        stmt = (
            select(WorkflowDecision)
            .where(WorkflowDecision.controller_id == controller_id)
            .order_by(WorkflowDecision.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_workflow(self, workflow_id: uuid.UUID) -> List[WorkflowDecision]:
        stmt = (
            select(WorkflowDecision)
            .where(WorkflowDecision.workflow_id == workflow_id)
            .order_by(WorkflowDecision.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AgentHealthRepository(BaseRepository[AgentHealth]):
    def __init__(self, db: AsyncSession):
        super().__init__(AgentHealth, db)

    async def get_by_agent(self, agent_id: str) -> Optional[AgentHealth]:
        stmt = select(AgentHealth).where(AgentHealth.agent_id == agent_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_all(self) -> List[AgentHealth]:
        stmt = select(AgentHealth).order_by(AgentHealth.agent_id.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class RetryHistoryRepository(BaseRepository[RetryHistory]):
    def __init__(self, db: AsyncSession):
        super().__init__(RetryHistory, db)

    async def list_by_controller(self, controller_id: uuid.UUID) -> List[RetryHistory]:
        stmt = (
            select(RetryHistory)
            .where(RetryHistory.controller_id == controller_id)
            .order_by(RetryHistory.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class FailureEventRepository(BaseRepository[FailureEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(FailureEvent, db)

    async def list_by_controller(self, controller_id: uuid.UUID) -> List[FailureEvent]:
        stmt = (
            select(FailureEvent)
            .where(FailureEvent.controller_id == controller_id)
            .order_by(FailureEvent.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class RollbackEventRepository(BaseRepository[RollbackEvent]):
    def __init__(self, db: AsyncSession):
        super().__init__(RollbackEvent, db)

    async def list_by_controller(self, controller_id: uuid.UUID) -> List[RollbackEvent]:
        stmt = (
            select(RollbackEvent)
            .where(RollbackEvent.controller_id == controller_id)
            .order_by(RollbackEvent.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ExecutionPlanRepository(BaseRepository[ExecutionPlan]):
    def __init__(self, db: AsyncSession):
        super().__init__(ExecutionPlan, db)

    async def get_by_controller(self, controller_id: uuid.UUID) -> Optional[ExecutionPlan]:
        stmt = select(ExecutionPlan).where(ExecutionPlan.controller_id == controller_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()


class ControllerLogRepository(BaseRepository[ControllerLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(ControllerLog, db)

    async def list_by_controller(self, controller_id: uuid.UUID) -> List[ControllerLog]:
        stmt = (
            select(ControllerLog)
            .where(ControllerLog.controller_id == controller_id)
            .order_by(ControllerLog.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
