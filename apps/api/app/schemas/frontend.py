"""
Pydantic v2 schemas for the Frontend Agent (Milestone 9).

Naming convention:
  *Read      – ORM → API response (from_attributes=True)
  *Payload   – internal agent output consumed by FrontendGenerationService
  *Request   – inbound API request body
  *Summary   – lightweight list-view response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── FrontendPage schemas ──────────────────────────────────────────────────────

class FrontendPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_id: uuid.UUID
    generation_id: uuid.UUID
    page_type: str
    route_path: str
    code: str
    metadata_json: Optional[dict] = None
    created_at: datetime


class FrontendPagePayload(BaseModel):
    page_type: str
    route_path: str
    code: str
    metadata_json: Optional[dict] = None


# ── FrontendComponent schemas ─────────────────────────────────────────────────

class FrontendComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    component_id: uuid.UUID
    generation_id: uuid.UUID
    component_name: str
    component_type: str
    code: str
    metadata_json: Optional[dict] = None
    created_at: datetime


class FrontendComponentPayload(BaseModel):
    component_name: str
    component_type: str
    code: str
    metadata_json: Optional[dict] = None


# ── FrontendForm schemas ──────────────────────────────────────────────────────

class FrontendFormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    form_id: uuid.UUID
    generation_id: uuid.UUID
    form_name: str
    fields_schema: Optional[dict] = None
    validation_schema: Optional[str] = None
    code: str
    created_at: datetime


class FrontendFormPayload(BaseModel):
    form_name: str
    fields_schema: Optional[dict] = None
    validation_schema: Optional[str] = None
    code: str


# ── FrontendHook schemas ──────────────────────────────────────────────────────

class FrontendHookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hook_id: uuid.UUID
    generation_id: uuid.UUID
    hook_name: str
    hook_type: str
    code: str
    created_at: datetime


class FrontendHookPayload(BaseModel):
    hook_name: str
    hook_type: str
    code: str


# ── FrontendTestReport schemas ────────────────────────────────────────────────

class FrontendTestReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    test_report_id: uuid.UUID
    generation_id: uuid.UUID
    test_type: str
    test_name: str
    test_code: str
    status: str
    created_at: datetime


class FrontendTestReportPayload(BaseModel):
    test_type: str
    test_name: str
    test_code: str


# ── UiDesignArtifact schemas ──────────────────────────────────────────────────

class UiDesignArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    generation_id: uuid.UUID
    artifact_name: str
    artifact_type: str
    content: str
    created_at: datetime


class UiDesignArtifactPayload(BaseModel):
    artifact_name: str
    artifact_type: str
    content: str


# ── FrontendGeneration composite schemas ──────────────────────────────────────

class FrontendGenerationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    status: str
    framework: str
    language: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FrontendGenerationRead(FrontendGenerationSummary):
    pass


class FrontendGenerationFullResponse(FrontendGenerationRead):
    """Complete generation with all child artifacts."""
    pages: List[FrontendPageRead] = Field(default_factory=list)
    components: List[FrontendComponentRead] = Field(default_factory=list)
    forms: List[FrontendFormRead] = Field(default_factory=list)
    hooks: List[FrontendHookRead] = Field(default_factory=list)
    test_reports: List[FrontendTestReportRead] = Field(default_factory=list)
    ui_design_artifacts: List[UiDesignArtifactRead] = Field(default_factory=list)


# ── Internal agent payload ────────────────────────────────────────────────────

class FrontendGenerationPayload(BaseModel):
    """Payload produced by FrontendAgent and consumed by FrontendGenerationService."""
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    framework: str = "Next.js 15"
    language: str = "TypeScript"
    notes: Optional[str] = None
    pages: List[FrontendPagePayload] = Field(default_factory=list)
    components: List[FrontendComponentPayload] = Field(default_factory=list)
    forms: List[FrontendFormPayload] = Field(default_factory=list)
    hooks: List[FrontendHookPayload] = Field(default_factory=list)
    test_reports: List[FrontendTestReportPayload] = Field(default_factory=list)
    ui_design_artifacts: List[UiDesignArtifactPayload] = Field(default_factory=list)


# ── API request bodies ────────────────────────────────────────────────────────

class GenerateFrontendRequest(BaseModel):
    """Body for POST /frontend/generate."""
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    backend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    framework: str = "Next.js 15"
    language: str = "TypeScript"


class RegenerateFrontendRequest(BaseModel):
    """Body for POST /frontend/generations/{id}/regenerate."""
    reason: Optional[str] = None
