"""
REST router for the DevOps Agent – Milestone 12.
Prefix: /api/v1/devops
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_devops_generation_service
from app.schemas.token import TokenData
from app.schemas.devops import (
    DevOpsGenerationSummary,
    DevOpsGenerationRead,
    DevOpsGenerationFullResponse,
    DockerArtifactRead,
    KubernetesArtifactRead,
    HelmArtifactRead,
    TerraformArtifactRead,
    CicdPipelineRead,
    DeploymentTemplateRead,
    GenerateDevOpsRequest,
    RegenerateDevOpsRequest,
)
from app.services.devops import DevOpsGenerationService

router = APIRouter(prefix="/devops", tags=["DevOps Agent"])


# ── POST /devops/generate ────────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger DevOps artifact generation and templates creation",
)
async def generate_devops(
    body: GenerateDevOpsRequest,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> dict:
    gen = await svc.trigger_generation(
        project_id=body.project_id,
        workflow_id=body.workflow_id,
        backend_generation_id=body.backend_generation_id,
        frontend_generation_id=body.frontend_generation_id,
        design_id=body.design_id,
        report_id=body.report_id,
    )
    return {
        "success": True,
        "data": {
            "generation_id": str(gen.generation_id),
            "status": gen.status,
            "message": (
                "DevOps generation started. "
                "Poll GET /devops/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /devops/generations/{generation_id} ───────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=DevOpsGenerationFullResponse,
    summary="Get full DevOps generation with all docker, k8s, helm, tf artifacts",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> DevOpsGenerationFullResponse:
    gen = await svc.get_full_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DevOpsGeneration '{generation_id}' not found",
        )

    dockers = await svc.list_docker_artifacts(generation_id)
    k8s = await svc.list_kubernetes_artifacts(generation_id)
    helms = await svc.list_helm_artifacts(generation_id)
    tfs = await svc.list_terraform_artifacts(generation_id)
    pipelines = await svc.list_cicd_pipelines(generation_id)
    templates = await svc.list_deployment_templates(generation_id)

    res_dict = {
        "generation_id": gen.generation_id,
        "project_id": gen.project_id,
        "workflow_id": gen.workflow_id,
        "backend_generation_id": gen.backend_generation_id,
        "frontend_generation_id": gen.frontend_generation_id,
        "design_id": gen.design_id,
        "report_id": gen.report_id,
        "status": gen.status,
        "notes": gen.notes,
        "created_at": gen.created_at,
        "updated_at": gen.updated_at,
        "docker_artifacts": dockers,
        "kubernetes_artifacts": k8s,
        "helm_artifacts": helms,
        "terraform_artifacts": tfs,
        "cicd_pipelines": pipelines,
        "deployment_templates": templates,
    }
    return DevOpsGenerationFullResponse.model_validate(res_dict)


# ── GET /devops/docker-artifacts/{artifact_id} ────────────────────────────────

@router.get(
    "/docker-artifacts/{artifact_id}",
    response_model=DockerArtifactRead,
    summary="Get docker artifact details by ID",
)
async def get_docker_artifact(
    artifact_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> DockerArtifactRead:
    art = await svc.docker_repo.get(artifact_id)
    if not art:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DockerArtifact '{artifact_id}' not found",
        )
    return DockerArtifactRead.model_validate(art)


# ── GET /devops/kubernetes-artifacts/{artifact_id} ─────────────────────────────

@router.get(
    "/kubernetes-artifacts/{artifact_id}",
    response_model=KubernetesArtifactRead,
    summary="Get kubernetes manifest by ID",
)
async def get_kubernetes_artifact(
    artifact_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> KubernetesArtifactRead:
    art = await svc.kubernetes_repo.get(artifact_id)
    if not art:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KubernetesArtifact '{artifact_id}' not found",
        )
    return KubernetesArtifactRead.model_validate(art)


# ── GET /devops/helm-artifacts/{artifact_id} ─────────────────────────────────

@router.get(
    "/helm-artifacts/{artifact_id}",
    response_model=HelmArtifactRead,
    summary="Get helm chart file by ID",
)
async def get_helm_artifact(
    artifact_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> HelmArtifactRead:
    art = await svc.helm_repo.get(artifact_id)
    if not art:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HelmArtifact '{artifact_id}' not found",
        )
    return HelmArtifactRead.model_validate(art)


# ── GET /devops/terraform-artifacts/{artifact_id} ──────────────────────────────

@router.get(
    "/terraform-artifacts/{artifact_id}",
    response_model=TerraformArtifactRead,
    summary="Get terraform config file by ID",
)
async def get_terraform_artifact(
    artifact_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> TerraformArtifactRead:
    art = await svc.terraform_repo.get(artifact_id)
    if not art:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TerraformArtifact '{artifact_id}' not found",
        )
    return TerraformArtifactRead.model_validate(art)


# ── GET /devops/pipelines/{pipeline_id} ───────────────────────────────────────

@router.get(
    "/pipelines/{pipeline_id}",
    response_model=CicdPipelineRead,
    summary="Get CI/CD pipeline configuration by ID",
)
async def get_cicd_pipeline(
    pipeline_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> CicdPipelineRead:
    pipe = await svc.pipeline_repo.get(pipeline_id)
    if not pipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CicdPipeline '{pipeline_id}' not found",
        )
    return CicdPipelineRead.model_validate(pipe)


# ── GET /devops/templates/{template_id} ───────────────────────────────────────

@router.get(
    "/templates/{template_id}",
    response_model=DeploymentTemplateRead,
    summary="Get deployment cloud template by ID",
)
async def get_deployment_template(
    template_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> DeploymentTemplateRead:
    temp = await svc.template_repo.get(template_id)
    if not temp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DeploymentTemplate '{template_id}' not found",
        )
    return DeploymentTemplateRead.model_validate(temp)


# ── POST /devops/generations/{generation_id}/regenerate ────────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger DevOps generation regeneration",
)
async def regenerate_devops(
    generation_id: uuid.UUID,
    body: RegenerateDevOpsRequest,
    _: TokenData = Depends(get_current_user),
    svc: DevOpsGenerationService = Depends(get_devops_generation_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DevOpsGeneration '{generation_id}' not found",
        )
    await svc.trigger_regeneration(
        generation_id=generation_id,
        workflow_id=gen.workflow_id,
        reason=body.reason,
    )
    return {
        "success": True,
        "data": {
            "generation_id": str(generation_id),
            "message": "DevOps regeneration triggered. The agent will produce new configuration templates shortly.",
        },
        "error": None,
    }
