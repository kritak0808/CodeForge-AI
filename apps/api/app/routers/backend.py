"""
REST router for the Backend Agent – Milestone 8.
Prefix: /api/v1/backend
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_backend_generation_service
from app.schemas.token import TokenData
from app.schemas.backend import (
    BackendGenerationSummary,
    BackendGenerationRead,
    BackendGenerationFullResponse,
    ApiEndpointRead,
    ServiceDefinitionRead,
    RepositoryDefinitionRead,
    BusinessRuleRead,
    ApiTestReportRead,
    GenerateBackendRequest,
    RegenerateBackendRequest,
)
from app.services.backend import BackendGenerationService

router = APIRouter(prefix="/backend", tags=["Backend Agent"])


async def _require_generation(
    generation_id: uuid.UUID,
    svc: BackendGenerationService,
) -> object:
    """Shared guard: 404 if generation not found."""
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BackendGeneration '{generation_id}' not found",
        )
    return gen


# ── POST /backend/generate ────────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger backend code generation for a workflow",
)
async def generate_backend(
    body: GenerateBackendRequest,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> dict:
    gen = await svc.trigger_generation(
        project_id=body.project_id,
        workflow_id=body.workflow_id,
        design_id=body.design_id,
        report_id=body.report_id,
        framework=body.framework,
        language=body.language,
    )
    return {
        "success": True,
        "data": {
            "generation_id": str(gen.generation_id),
            "status": gen.status,
            "message": (
                "Backend generation started. "
                "Poll GET /backend/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /backend/generations ──────────────────────────────────────────────────

@router.get(
    "/generations",
    response_model=List[BackendGenerationSummary],
    summary="List all backend generations for a project",
)
async def list_generations(
    project_id: uuid.UUID = Query(..., description="Project UUID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[BackendGenerationSummary]:
    gens = await svc.list_generations_for_project(project_id, skip=skip, limit=limit)
    return [BackendGenerationSummary.model_validate(g) for g in gens]


# ── GET /backend/generations/{id} ────────────────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=BackendGenerationFullResponse,
    summary="Get full backend generation with all artifacts",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> BackendGenerationFullResponse:
    gen = await svc.get_full_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BackendGeneration '{generation_id}' not found",
        )
    return BackendGenerationFullResponse.model_validate(gen)


# ── GET /backend/generations/{id}/endpoints ───────────────────────────────────

@router.get(
    "/generations/{generation_id}/endpoints",
    response_model=List[ApiEndpointRead],
    summary="List generated API endpoints",
)
async def list_endpoints(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[ApiEndpointRead]:
    await _require_generation(generation_id, svc)
    return [
        ApiEndpointRead.model_validate(ep)
        for ep in await svc.list_endpoints(generation_id)
    ]


# ── GET /backend/generations/{id}/services ────────────────────────────────────

@router.get(
    "/generations/{generation_id}/services",
    response_model=List[ServiceDefinitionRead],
    summary="List generated service definitions",
)
async def list_services(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[ServiceDefinitionRead]:
    await _require_generation(generation_id, svc)
    return [
        ServiceDefinitionRead.model_validate(s)
        for s in await svc.list_services(generation_id)
    ]


# ── GET /backend/generations/{id}/repositories ───────────────────────────────

@router.get(
    "/generations/{generation_id}/repositories",
    response_model=List[RepositoryDefinitionRead],
    summary="List generated repository definitions",
)
async def list_repositories(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[RepositoryDefinitionRead]:
    await _require_generation(generation_id, svc)
    return [
        RepositoryDefinitionRead.model_validate(r)
        for r in await svc.list_repositories(generation_id)
    ]


# ── GET /backend/generations/{id}/rules ──────────────────────────────────────

@router.get(
    "/generations/{generation_id}/rules",
    response_model=List[BusinessRuleRead],
    summary="List generated business rules",
)
async def list_rules(
    generation_id: uuid.UUID,
    rule_type: Optional[str] = Query(
        None,
        description="Filter by rule type: VALIDATION, AUTHORIZATION, BUSINESS_LOGIC, etc.",
    ),
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[BusinessRuleRead]:
    await _require_generation(generation_id, svc)
    return [
        BusinessRuleRead.model_validate(r)
        for r in await svc.list_rules(generation_id, rule_type=rule_type)
    ]


# ── GET /backend/generations/{id}/tests ──────────────────────────────────────

@router.get(
    "/generations/{generation_id}/tests",
    response_model=List[ApiTestReportRead],
    summary="List generated test cases",
)
async def list_tests(
    generation_id: uuid.UUID,
    test_type: Optional[str] = Query(
        None, description="Filter by test type: unit, integration, api, e2e"
    ),
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> List[ApiTestReportRead]:
    await _require_generation(generation_id, svc)
    return [
        ApiTestReportRead.model_validate(t)
        for t in await svc.list_tests(generation_id, test_type=test_type)
    ]


# ── POST /backend/generations/{id}/regenerate ─────────────────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger regeneration of a backend generation",
)
async def regenerate_backend(
    generation_id: uuid.UUID,
    body: RegenerateBackendRequest,
    _: TokenData = Depends(get_current_user),
    svc: BackendGenerationService = Depends(get_backend_generation_service),
) -> dict:
    gen = await _require_generation(generation_id, svc)
    await svc.trigger_regeneration(
        generation_id=generation_id,
        workflow_id=gen.workflow_id,
        reason=body.reason,
    )
    return {
        "success": True,
        "data": {
            "generation_id": str(generation_id),
            "message": "Regeneration triggered. The agent will produce new code shortly.",
        },
        "error": None,
    }
