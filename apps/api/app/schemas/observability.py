"""
Pydantic schemas for the Observability & Monitoring Platform (Milestone 15).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Child metric payloads (inbound from agent worker) ─────────────────────────

class AgentMetricPayload(BaseModel):
    agent_name: str
    duration_ms: float = 0.0
    tokens_used: int = 0
    success_rate: float = 1.0
    error_count: int = 0
    extra_metadata: Optional[dict] = None


class WorkflowMetricPayload(BaseModel):
    workflow_id: Optional[uuid.UUID] = None
    step_name: str
    duration_ms: float = 0.0
    status: str = "COMPLETED"
    throughput_rps: Optional[float] = None


class ApiMetricPayload(BaseModel):
    endpoint: str
    method: str = "GET"
    avg_latency_ms: float = 0.0
    p99_latency_ms: Optional[float] = None
    error_rate: float = 0.0
    request_count: int = 0


class SystemMetricPayload(BaseModel):
    service_name: str
    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    disk_pct: float = 0.0


class ErrorEventPayload(BaseModel):
    source: str
    severity: str = "ERROR"
    message: str
    stack_trace: Optional[str] = None
    context: Optional[dict] = None


class AlertRulePayload(BaseModel):
    rule_name: str
    metric_name: str
    operator: str = "gt"
    threshold: float
    severity: str = "WARNING"
    is_active: bool = True


class AlertEventPayload(BaseModel):
    rule_name: str
    current_value: float
    threshold: float
    severity: str = "WARNING"
    message: str
    status: str = "OPEN"


# ── Root generation payload ───────────────────────────────────────────────────

class ObservabilityGenerationPayload(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    agent_metrics: List[AgentMetricPayload] = Field(default_factory=list)
    workflow_metrics: List[WorkflowMetricPayload] = Field(default_factory=list)
    api_metrics: List[ApiMetricPayload] = Field(default_factory=list)
    system_metrics: List[SystemMetricPayload] = Field(default_factory=list)
    error_events: List[ErrorEventPayload] = Field(default_factory=list)
    alert_rules: List[AlertRulePayload] = Field(default_factory=list)
    alert_events: List[AlertEventPayload] = Field(default_factory=list)


# ── REST request bodies ───────────────────────────────────────────────────────

class GenerateObservabilityRequest(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None


class RegenerateObservabilityRequest(BaseModel):
    reason: Optional[str] = None


# ── Read schemas (outbound) ───────────────────────────────────────────────────

class ObservabilityGenerationRead(BaseModel):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentMetricRead(BaseModel):
    metric_id: uuid.UUID
    generation_id: uuid.UUID
    agent_name: str
    duration_ms: float
    tokens_used: int
    success_rate: float
    error_count: int
    extra_metadata: Optional[dict] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowMetricRead(BaseModel):
    metric_id: uuid.UUID
    generation_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    step_name: str
    duration_ms: float
    status: str
    throughput_rps: Optional[float] = None
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApiMetricRead(BaseModel):
    metric_id: uuid.UUID
    generation_id: uuid.UUID
    endpoint: str
    method: str
    avg_latency_ms: float
    p99_latency_ms: Optional[float] = None
    error_rate: float
    request_count: int
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SystemMetricRead(BaseModel):
    metric_id: uuid.UUID
    generation_id: uuid.UUID
    service_name: str
    cpu_pct: float
    memory_pct: float
    disk_pct: float
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ErrorEventRead(BaseModel):
    event_id: uuid.UUID
    generation_id: uuid.UUID
    source: str
    severity: str
    message: str
    stack_trace: Optional[str] = None
    context: Optional[dict] = None
    occurred_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertRuleRead(BaseModel):
    rule_id: uuid.UUID
    generation_id: uuid.UUID
    rule_name: str
    metric_name: str
    operator: str
    threshold: float
    severity: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertEventRead(BaseModel):
    alert_id: uuid.UUID
    generation_id: uuid.UUID
    rule_id: Optional[uuid.UUID] = None
    rule_name: str
    current_value: float
    threshold: float
    severity: str
    message: str
    status: str
    fired_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ObservabilityGenerationFullResponse(BaseModel):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    agent_metrics: List[AgentMetricRead] = Field(default_factory=list)
    workflow_metrics: List[WorkflowMetricRead] = Field(default_factory=list)
    api_metrics: List[ApiMetricRead] = Field(default_factory=list)
    system_metrics: List[SystemMetricRead] = Field(default_factory=list)
    error_events: List[ErrorEventRead] = Field(default_factory=list)
    alert_rules: List[AlertRuleRead] = Field(default_factory=list)
    alert_events: List[AlertEventRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
