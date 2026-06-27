"""
Pydantic schemas for the Autonomous SDLC Controller Agent (Milestone 17).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, Field


# ── REST Request Schemas ──────────────────────────────────────────────────────

class StartControllerRequest(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None


class PauseControllerRequest(BaseModel):
    workflow_id: uuid.UUID


class ResumeControllerRequest(BaseModel):
    workflow_id: uuid.UUID


class RetryControllerRequest(BaseModel):
    workflow_id: uuid.UUID
    step: str


class RollbackControllerRequest(BaseModel):
    workflow_id: uuid.UUID
    target_step: str
    reason: str


class CancelControllerRequest(BaseModel):
    workflow_id: uuid.UUID


# ── Payload Schemas (inbound from agent worker) ───────────────────────────────

class WorkflowDecisionPayload(BaseModel):
    step: str
    decision_type: str  # ROUTE, RETRY, ROLLBACK, APPROVE, COMPLETE, FAIL
    reason: str
    action_taken: str
    metadata_json: Optional[dict] = None


class AgentHealthPayload(BaseModel):
    agent_id: str
    status: str  # HEALTHY, DEGRADED, UNHEALTHY
    error_count: int = 0
    avg_response_time: float = 0.0
    metadata_json: Optional[dict] = None


class RetryHistoryPayload(BaseModel):
    step: str
    retry_attempt: int
    max_retries: int = 3
    error_message: Optional[str] = None
    next_retry_at: Optional[datetime] = None


class FailureEventPayload(BaseModel):
    step: str
    error_type: str
    error_message: str
    severity: str = "ERROR"  # WARNING, ERROR, CRITICAL
    is_resolved: bool = False


class RollbackEventPayload(BaseModel):
    source_step: str
    target_step: str
    reason: str
    status: str = "PENDING"


class ExecutionPlanPayload(BaseModel):
    steps_json: List[str]
    current_step_index: int = 0
    is_optimized: bool = False


class ControllerLogPayload(BaseModel):
    level: str = "INFO"
    message: str


class AutonomousControllerPayload(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str = "ACTIVE"
    current_step: str
    budget_limit: float = 0.0
    decisions: List[WorkflowDecisionPayload] = Field(default_factory=list)
    retries: List[RetryHistoryPayload] = Field(default_factory=list)
    failures: List[FailureEventPayload] = Field(default_factory=list)
    rollbacks: List[RollbackEventPayload] = Field(default_factory=list)
    execution_plans: List[ExecutionPlanPayload] = Field(default_factory=list)
    logs: List[ControllerLogPayload] = Field(default_factory=list)


# ── Read Schemas (outbound) ───────────────────────────────────────────────────

class AutonomousControllerRead(BaseModel):
    controller_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    current_step: str
    budget_limit: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowDecisionRead(BaseModel):
    decision_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    step: str
    decision_type: str
    reason: str
    action_taken: str
    metadata_json: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentHealthRead(BaseModel):
    health_id: uuid.UUID
    agent_id: str
    status: str
    last_heartbeat: Optional[datetime] = None
    error_count: int
    avg_response_time: float
    metadata_json: Optional[dict] = None

    model_config = {"from_attributes": True}


class RetryHistoryRead(BaseModel):
    retry_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    step: str
    retry_attempt: int
    max_retries: int
    error_message: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FailureEventRead(BaseModel):
    failure_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    step: str
    error_type: str
    error_message: str
    severity: str
    is_resolved: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RollbackEventRead(BaseModel):
    rollback_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    source_step: str
    target_step: str
    reason: str
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExecutionPlanRead(BaseModel):
    plan_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    steps_json: List[str]
    current_step_index: int
    is_optimized: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ControllerLogRead(BaseModel):
    log_id: uuid.UUID
    controller_id: uuid.UUID
    workflow_id: uuid.UUID
    level: str
    message: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AutonomousControllerFullResponse(BaseModel):
    controller_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    current_step: str
    budget_limit: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    decisions: List[WorkflowDecisionRead] = Field(default_factory=list)
    retries: List[RetryHistoryRead] = Field(default_factory=list)
    failures: List[FailureEventRead] = Field(default_factory=list)
    rollbacks: List[RollbackEventRead] = Field(default_factory=list)
    execution_plans: List[ExecutionPlanRead] = Field(default_factory=list)
    logs: List[ControllerLogRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
