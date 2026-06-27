from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.repositories.base import BaseRepository
from app.models import Workflow, WorkflowState, Task, Approval, Metric, Agent

class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, db):
        super().__init__(Workflow, db)

    async def get_workflow_details(self, workflow_id: UUID) -> Optional[Workflow]:
        # Perform deep eager loading of states, tasks, approvals, and metrics
        query = (
            select(Workflow)
            .filter(Workflow.workflow_id == workflow_id)
            .options(
                selectinload(Workflow.states),
                selectinload(Workflow.tasks),
                selectinload(Workflow.approvals),
                selectinload(Workflow.metrics)
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_project_workflows(self, project_id: UUID) -> List[Workflow]:
        query = select(Workflow).filter(Workflow.project_id == project_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

class WorkflowStateRepository(BaseRepository[WorkflowState]):
    def __init__(self, db):
        super().__init__(WorkflowState, db)

    async def get_active_state(self, workflow_id: UUID) -> Optional[WorkflowState]:
        query = (
            select(WorkflowState)
            .filter(WorkflowState.workflow_id == workflow_id, WorkflowState.exited_at == None)
            .order_by(WorkflowState.entered_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().first()

class TaskRepository(BaseRepository[Task]):
    def __init__(self, db):
        super().__init__(Task, db)

    async def get_workflow_tasks(self, workflow_id: UUID) -> List[Task]:
        query = select(Task).filter(Task.workflow_id == workflow_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

class ApprovalRepository(BaseRepository[Approval]):
    def __init__(self, db):
        super().__init__(Approval, db)

    async def get_pending_approvals(self) -> List[Approval]:
        query = select(Approval).filter(Approval.status == "PENDING")
        result = await self.db.execute(query)
        return list(result.scalars().all())

class MetricRepository(BaseRepository[Metric]):
    def __init__(self, db):
        super().__init__(Metric, db)
