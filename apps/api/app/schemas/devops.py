"""
Pydantic v2 schemas for the DevOps Agent (Milestone 12).

Naming convention:
  *Read      – ORM → API response (from_attributes=True)
  *Payload   – internal agent output consumed by DevOpsGenerationService
  *Request   – inbound API request body
  *Summary   – lightweight list-view response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── DockerArtifact schemas ──────────────────────────────────────────────────

class DockerArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    generation_id: uuid.UUID
    file_name: str
    content: str
    created_at: datetime


class DockerArtifactPayload(BaseModel):
    file_name: str
    content: str


# ── KubernetesArtifact schemas ──────────────────────────────────────────────

class KubernetesArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    generation_id: uuid.UUID
    manifest_name: str
    manifest_type: str
    content: str
    created_at: datetime


class KubernetesArtifactPayload(BaseModel):
    manifest_name: str
    manifest_type: str
    content: str


# ── HelmArtifact schemas ─────────────────────────────────────────────────────

class HelmArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    generation_id: uuid.UUID
    file_path: str
    content: str
    created_at: datetime


class HelmArtifactPayload(BaseModel):
    file_path: str
    content: str


# ── TerraformArtifact schemas ────────────────────────────────────────────────

class TerraformArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    generation_id: uuid.UUID
    file_path: str
    content: str
    created_at: datetime


class TerraformArtifactPayload(BaseModel):
    file_path: str
    content: str


# ── CicdPipeline schemas ─────────────────────────────────────────────────────

class CicdPipelineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pipeline_id: uuid.UUID
    generation_id: uuid.UUID
    provider: str
    content: str
    created_at: datetime


class CicdPipelinePayload(BaseModel):
    provider: str
    content: str


# ── DeploymentTemplate schemas ───────────────────────────────────────────────

class DeploymentTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    generation_id: uuid.UUID
    target_platform: str
    content: str
    created_at: datetime


class DeploymentTemplatePayload(BaseModel):
    target_platform: str
    content: str


# ── DevOpsGeneration composite schemas ────────────────────────────────────────

class DevOpsGenerationSummary(BaseModel):
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


class DevOpsGenerationRead(DevOpsGenerationSummary):
    pass


class DevOpsGenerationFullResponse(DevOpsGenerationRead):
    """Complete generation with all child artifacts."""
    docker_artifacts: List[DockerArtifactRead] = Field(default_factory=list)
    kubernetes_artifacts: List[KubernetesArtifactRead] = Field(default_factory=list)
    helm_artifacts: List[HelmArtifactRead] = Field(default_factory=list)
    terraform_artifacts: List[TerraformArtifactRead] = Field(default_factory=list)
    cicd_pipelines: List[CicdPipelineRead] = Field(default_factory=list)
    deployment_templates: List[DeploymentTemplateRead] = Field(default_factory=list)


# ── Internal agent payload ───────────────────────────────────────────────────

class DevOpsGenerationPayload(BaseModel):
    """Payload produced by DevOpsAgent and consumed by DevOpsGenerationService."""
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    docker_artifacts: List[DockerArtifactPayload] = Field(default_factory=list)
    kubernetes_artifacts: List[KubernetesArtifactPayload] = Field(default_factory=list)
    helm_artifacts: List[HelmArtifactPayload] = Field(default_factory=list)
    terraform_artifacts: List[TerraformArtifactPayload] = Field(default_factory=list)
    cicd_pipelines: List[CicdPipelinePayload] = Field(default_factory=list)
    deployment_templates: List[DeploymentTemplatePayload] = Field(default_factory=list)


# ── API request bodies ────────────────────────────────────────────────────────

class GenerateDevOpsRequest(BaseModel):
    """Body for POST /devops/generate."""
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None


class RegenerateDevOpsRequest(BaseModel):
    """Body for POST /devops/generations/{id}/regenerate."""
    reason: Optional[str] = None
