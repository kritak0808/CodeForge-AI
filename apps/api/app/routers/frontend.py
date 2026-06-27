"""
REST router for the Frontend Agent – Milestone 9.
Prefix: /api/v1/frontend
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_frontend_generation_service
from app.schemas.token import TokenData
from app.schemas.frontend import (
    FrontendGenerationSummary,
    FrontendGenerationRead,
    FrontendGenerationFullResponse,
    FrontendPageRead,
    FrontendComponentRead,
    FrontendFormRead,
    FrontendHookRead,
    GenerateFrontendRequest,
    RegenerateFrontendRequest,
)
from app.services.frontend import FrontendGenerationService

router = APIRouter(prefix="/frontend", tags=["Frontend Agent"])


# ── POST /frontend/generate ──────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger frontend code generation for a workflow",
)
async def generate_frontend(
    body: GenerateFrontendRequest,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> dict:
    gen = await svc.trigger_generation(
        project_id=body.project_id,
        workflow_id=body.workflow_id,
        backend_generation_id=body.backend_generation_id,
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
                "Frontend generation started. "
                "Poll GET /frontend/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /frontend/generations/{generation_id} ─────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=FrontendGenerationFullResponse,
    summary="Get full frontend generation with all artifacts",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> FrontendGenerationFullResponse:
    gen = await svc.get_full_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendGeneration '{generation_id}' not found",
        )
    
    # Enrich child relations manually if not fully loaded by lazy-load configs
    pages = await svc.list_pages(generation_id)
    components = await svc.list_components(generation_id)
    forms = await svc.list_forms(generation_id)
    hooks = await svc.list_hooks(generation_id)
    tests = await svc.list_tests(generation_id)
    ui_artifacts = await svc.list_ui_design_artifacts(generation_id)

    # Return validated model
    res_dict = {
        "generation_id": gen.generation_id,
        "project_id": gen.project_id,
        "workflow_id": gen.workflow_id,
        "backend_generation_id": gen.backend_generation_id,
        "design_id": gen.design_id,
        "report_id": gen.report_id,
        "status": gen.status,
        "framework": gen.framework,
        "language": gen.language,
        "notes": gen.notes,
        "created_at": gen.created_at,
        "updated_at": gen.updated_at,
        "pages": pages,
        "components": components,
        "forms": forms,
        "hooks": hooks,
        "test_reports": tests,
        "ui_design_artifacts": ui_artifacts
    }
    return FrontendGenerationFullResponse.model_validate(res_dict)


# ── GET /frontend/pages/{page_id} ─────────────────────────────────────────────

@router.get(
    "/pages/{page_id}",
    response_model=FrontendPageRead,
    summary="Get generated frontend page by ID",
)
async def get_page(
    page_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> FrontendPageRead:
    page = await svc.page_repo.get(page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendPage '{page_id}' not found",
        )
    return FrontendPageRead.model_validate(page)


# ── GET /frontend/components/{component_id} ───────────────────────────────────

@router.get(
    "/components/{component_id}",
    response_model=FrontendComponentRead,
    summary="Get generated frontend component by ID",
)
async def get_component(
    component_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> FrontendComponentRead:
    comp = await svc.component_repo.get(component_id)
    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendComponent '{component_id}' not found",
        )
    return FrontendComponentRead.model_validate(comp)


# ── GET /frontend/forms/{form_id} ─────────────────────────────────────────────

@router.get(
    "/forms/{form_id}",
    response_model=FrontendFormRead,
    summary="Get generated form by ID",
)
async def get_form(
    form_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> FrontendFormRead:
    form = await svc.form_repo.get(form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendForm '{form_id}' not found",
        )
    return FrontendFormRead.model_validate(form)


# ── GET /frontend/hooks/{hook_id} ─────────────────────────────────────────────

@router.get(
    "/hooks/{hook_id}",
    response_model=FrontendHookRead,
    summary="Get generated React Query or State hook by ID",
)
async def get_hook(
    hook_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> FrontendHookRead:
    hook = await svc.hook_repo.get(hook_id)
    if not hook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendHook '{hook_id}' not found",
        )
    return FrontendHookRead.model_validate(hook)


# ── POST /frontend/generations/{generation_id}/regenerate ─────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger regeneration of frontend artifacts",
)
async def regenerate_frontend(
    generation_id: uuid.UUID,
    body: RegenerateFrontendRequest,
    _: TokenData = Depends(get_current_user),
    svc: FrontendGenerationService = Depends(get_frontend_generation_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FrontendGeneration '{generation_id}' not found",
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
            "message": "Regeneration triggered. The agent will produce new frontend code shortly.",
        },
        "error": None,
    }
