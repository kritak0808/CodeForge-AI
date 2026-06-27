from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class AgentResponse(BaseModel):
    agent_id: str
    name: str
    role_description: str
    llm_model: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class WorkflowBase(BaseModel):
    project_id: UUID

class WorkflowCreate(WorkflowBase):
    # requirements is optional — a workflow can be started with just a project_id
    requirements: Optional[str] = None

class WorkflowResponse(WorkflowBase):
    workflow_id: UUID
    current_state: str
    # Frontend-facing status derived from current_state
    status: str
    tasks_completed: int = 0
    tasks_total: int = 0
    triggered_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WorkflowStateResponse(BaseModel):
    state_id: UUID
    workflow_id: UUID
    state: str
    metadata_json: Optional[Dict[str, Any]] = None
    entered_at: datetime
    exited_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TaskResponse(BaseModel):
    task_id: UUID
    workflow_id: UUID
    agent_id: str
    title: str
    description: str
    status: str
    depends_on: Optional[List[str]] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ApprovalResponse(BaseModel):
    approval_id: UUID
    workflow_id: UUID
    approver_id: Optional[UUID] = None
    approval_type: str
    status: str
    artifact_payload: Dict[str, Any]
    comments: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ApprovalDecision(BaseModel):
    status: str  # APPROVED, REJECTED
    comments: Optional[str] = None

class MetricResponse(BaseModel):
    metric_id: UUID
    workflow_id: UUID
    agent_id: str
    tokens_consumed: int
    cost_usd: float
    latency_ms: int
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WorkflowDetailsResponse(WorkflowResponse):
    states: List[WorkflowStateResponse] = []
    tasks: List[TaskResponse] = []
    approvals: List[ApprovalResponse] = []
    metrics: List[MetricResponse] = []

    model_config = ConfigDict(from_attributes=True)
