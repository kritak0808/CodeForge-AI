from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class WorkflowStateModel(BaseModel):
    workflow_id: str
    project_id: str
    current_state: str
    current_agent: Optional[str] = None
    workflow_context: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    cost_metrics: Dict[str, float] = Field(default_factory=dict)
    token_metrics: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TaskMessage(BaseModel):
    task_id: str
    workflow_id: str
    agent_id: str
    command: str
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TaskResult(BaseModel):
    task_id: str
    workflow_id: str
    agent_id: str
    status: str  # COMPLETED, FAILED, PAUSED
    output: Any
    logs: str
    tokens: int = 0
    cost: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ApprovalRequest(BaseModel):
    approval_id: str
    workflow_id: str
    approval_type: str  # Architecture, Security, Deployment
    status: str  # PENDING, APPROVED, REJECTED
    artifact_payload: Dict[str, Any]
    comments: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
