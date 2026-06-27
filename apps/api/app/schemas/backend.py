"""
Pydantic v2 schemas for the Backend Agent (Milestone 8).

Naming convention:
  *Read      – ORM → API response (from_attributes=True)
  *Payload   – internal agent output consumed by BackendGenerationService
  *Request   – inbound API request body
  *Summary   – lightweight list-view response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── ApiEndpoint schemas ───────────────────────────────────────────────────────

class ApiEndpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    endpoint_id: uuid.UUID
    generation_id: uuid.UUID
    method: str
    path: str
    summary: Optional[str] = None
    request_schema: Optional[str] = None
    response_schema: Optional[str] = None
    router_code: Optional[str] = None
    auth_required: bool = True
    rate_limited: bool = False
    created_at: datetime


class ApiEndpointPayload(BaseModel):
    """Internal agent output for a single endpoint."""
    method: str
    path: str
    summary: Optional[str] = None
    request_schema: Optional[str] = None
    response_schema: Optional[str] = None
    router_code: Optional[str] = None
    auth_required: bool = True
    rate_limited: bool = False


# ── ServiceDefinition schemas ─────────────────────────────────────────────────

class ServiceDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_id: uuid.UUID
    generation_id: uuid.UUID
    service_name: str
    description: Optional[str] = None
    code: str
    dependencies: Optional[str] = None
    created_at: datetime


class ServiceDefinitionPayload(BaseModel):
    service_name: str
    description: Optional[str] = None
    code: str
    dependencies: Optional[str] = None


# ── RepositoryDefinition schemas ──────────────────────────────────────────────

class RepositoryDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repo_def_id: uuid.UUID
    generation_id: uuid.UUID
    repo_name: str
    model_name: str
    code: str
    created_at: datetime


class RepositoryDefinitionPayload(BaseModel):
    repo_name: str
    model_name: str
    code: str


# ── BusinessRule schemas ──────────────────────────────────────────────────────

class BusinessRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: uuid.UUID
    generation_id: uuid.UUID
    rule_name: str
    description: Optional[str] = None
    rule_type: str
    code: str
    created_at: datetime


class BusinessRulePayload(BaseModel):
    rule_name: str
    description: Optional[str] = None
    rule_type: str = "BUSINESS_LOGIC"
    code: str


# ── ApiTestReport schemas ─────────────────────────────────────────────────────

class ApiTestReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_report_id: uuid.UUID
    generation_id: uuid.UUID
    test_type: str
    test_name: str
    test_code: str
    status: str
    created_at: datetime


class ApiTestReportPayload(BaseModel):
    test_type: str = "integration"
    test_name: str
    test_code: str


# ── BackendGeneration composite schemas ───────────────────────────────────────

class BackendGenerationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    status: str
    framework: str
    language: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BackendGenerationRead(BackendGenerationSummary):
    openapi_spec: Optional[str] = None


class BackendGenerationFullResponse(BackendGenerationRead):
    """Complete generation with all child artifacts."""
    endpoints: List[ApiEndpointRead] = Field(default_factory=list)
    services: List[ServiceDefinitionRead] = Field(default_factory=list)
    repositories: List[RepositoryDefinitionRead] = Field(default_factory=list)
    rules: List[BusinessRuleRead] = Field(default_factory=list)
    test_reports: List[ApiTestReportRead] = Field(default_factory=list)


# ── Internal agent payload ────────────────────────────────────────────────────

class BackendGenerationPayload(BaseModel):
    """Payload produced by BackendAgent and consumed by BackendGenerationService."""
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    framework: str = "FastAPI"
    language: str = "Python"
    openapi_spec: Optional[str] = None
    notes: Optional[str] = None
    endpoints: List[ApiEndpointPayload] = Field(default_factory=list)
    services: List[ServiceDefinitionPayload] = Field(default_factory=list)
    repositories: List[RepositoryDefinitionPayload] = Field(default_factory=list)
    rules: List[BusinessRulePayload] = Field(default_factory=list)
    test_reports: List[ApiTestReportPayload] = Field(default_factory=list)


# ── API request bodies ────────────────────────────────────────────────────────

class GenerateBackendRequest(BaseModel):
    """Body for POST /backend/generate."""
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    framework: str = "FastAPI"
    language: str = "Python"


class RegenerateBackendRequest(BaseModel):
    """Body for POST /backend/generations/{id}/regenerate."""
    reason: Optional[str] = None
