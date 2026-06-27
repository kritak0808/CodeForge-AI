"""
Pydantic v2 schemas for the Security Agent (Milestone 11).

Naming convention:
  *Read      – ORM → API response (from_attributes=True)
  *Payload   – internal agent output consumed by SecurityGenerationService
  *Request   – inbound API request body
  *Summary   – lightweight list-view response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── ThreatModel schemas ──────────────────────────────────────────────────────

class ThreatModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: uuid.UUID
    generation_id: uuid.UUID
    threat_source: str
    vulnerability: str
    impact: str
    risk_level: str
    mitigation: Optional[str] = None
    created_at: datetime


class ThreatModelPayload(BaseModel):
    threat_source: str
    vulnerability: str
    impact: str
    risk_level: str
    mitigation: Optional[str] = None


# ── SecurityFinding schemas ──────────────────────────────────────────────────

class SecurityFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: uuid.UUID
    generation_id: uuid.UUID
    title: str
    description: str
    severity: str
    remediation: Optional[str] = None
    finding_type: str
    metadata_json: Optional[dict] = None
    created_at: datetime


class SecurityFindingPayload(BaseModel):
    title: str
    description: str
    severity: str
    remediation: Optional[str] = None
    finding_type: str
    metadata_json: Optional[dict] = None


# ── DependencyScan schemas ───────────────────────────────────────────────────

class DependencyScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: uuid.UUID
    generation_id: uuid.UUID
    package_name: str
    installed_version: str
    latest_version: Optional[str] = None
    vulnerabilities_json: Optional[dict] = None
    status: str
    created_at: datetime


class DependencyScanPayload(BaseModel):
    package_name: str
    installed_version: str
    latest_version: Optional[str] = None
    vulnerabilities_json: Optional[dict] = None
    status: str


# ── SecretScan schemas ───────────────────────────────────────────────────────

class SecretScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: uuid.UUID
    generation_id: uuid.UUID
    file_path: str
    secret_type: str
    line_number: Optional[int] = None
    status: str
    created_at: datetime


class SecretScanPayload(BaseModel):
    file_path: str
    secret_type: str
    line_number: Optional[int] = None
    status: str


# ── RbacAudit schemas ────────────────────────────────────────────────────────

class RbacAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: uuid.UUID
    generation_id: uuid.UUID
    role_name: str
    permissions_json: Optional[dict] = None
    audit_result: str
    status: str
    created_at: datetime


class RbacAuditPayload(BaseModel):
    role_name: str
    permissions_json: Optional[dict] = None
    audit_result: str
    status: str


# ── SecurityReport schemas ───────────────────────────────────────────────────

class SecurityReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    generation_id: uuid.UUID
    report_name: str
    overall_risk_score: float
    recommendations_json: Optional[dict] = None
    summary: Optional[str] = None
    created_at: datetime


class SecurityReportPayload(BaseModel):
    report_name: str
    overall_risk_score: float
    recommendations_json: Optional[dict] = None
    summary: Optional[str] = None


# ── SecurityGeneration composite schemas ──────────────────────────────────────

class SecurityGenerationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SecurityGenerationRead(SecurityGenerationSummary):
    pass


class SecurityGenerationFullResponse(SecurityGenerationRead):
    """Complete generation with all child artifacts."""
    threat_models: List[ThreatModelRead] = Field(default_factory=list)
    security_findings: List[SecurityFindingRead] = Field(default_factory=list)
    dependency_scans: List[DependencyScanRead] = Field(default_factory=list)
    secret_scans: List[SecretScanRead] = Field(default_factory=list)
    rbac_audits: List[RbacAuditRead] = Field(default_factory=list)
    security_reports: List[SecurityReportRead] = Field(default_factory=list)


# ── Internal agent payload ────────────────────────────────────────────────────

class SecurityGenerationPayload(BaseModel):
    """Payload produced by SecurityAgent and consumed by SecurityGenerationService."""
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    threat_models: List[ThreatModelPayload] = Field(default_factory=list)
    security_findings: List[SecurityFindingPayload] = Field(default_factory=list)
    dependency_scans: List[DependencyScanPayload] = Field(default_factory=list)
    secret_scans: List[SecretScanPayload] = Field(default_factory=list)
    rbac_audits: List[RbacAuditPayload] = Field(default_factory=list)
    security_reports: List[SecurityReportPayload] = Field(default_factory=list)


# ── API request bodies ────────────────────────────────────────────────────────

class GenerateSecurityRequest(BaseModel):
    """Body for POST /security/generate."""
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None


class RegenerateSecurityRequest(BaseModel):
    """Body for POST /security/generations/{id}/regenerate."""
    reason: Optional[str] = None
