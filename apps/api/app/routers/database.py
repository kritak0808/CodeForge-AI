"""
REST router for the Database Agent – Milestone 7.
Prefix: /api/v1/database
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_database_design_service
from app.schemas.token import TokenData
from app.schemas.database import (
    DatabaseDesignSummary,
    DatabaseDesignRead,
    DatabaseDesignFullResponse,
    DatabaseEntityRead,
    DatabaseRelationshipRead,
    DatabaseIndexRead,
    MigrationPlanRead,
    QueryOptimizationReportRead,
    RegenerateRequest,
)
from app.services.database import DatabaseDesignService

router = APIRouter(prefix="/database", tags=["Database Agent"])


async def _require_design(
    design_id: uuid.UUID,
    svc: DatabaseDesignService,
) -> object:
    """Shared guard: 404 if design not found."""
    design = await svc.get_design(design_id)
    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DatabaseDesign '{design_id}' not found",
        )
    return design


# ── GET /database/designs ────────────────────────────────────────────────

@router.get(
    "/designs",
    response_model=List[DatabaseDesignSummary],
    summary="List all database designs for a project",
)
async def list_designs(
    project_id: uuid.UUID = Query(..., description="Project UUID to scope results"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[DatabaseDesignSummary]:
    designs = await svc.list_designs_for_project(project_id, skip=skip, limit=limit)
    return [DatabaseDesignSummary.model_validate(d) for d in designs]


# ── GET /database/designs/{design_id} ────────────────────────────────────

@router.get(
    "/designs/{design_id}",
    response_model=DatabaseDesignFullResponse,
    summary="Get full database design with all child artifacts",
)
async def get_design(
    design_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> DatabaseDesignFullResponse:
    design = await svc.get_full_design(design_id)
    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DatabaseDesign '{design_id}' not found",
        )
    return DatabaseDesignFullResponse.model_validate(design)


# ── GET /database/designs/{design_id}/entities ───────────────────────────

@router.get(
    "/designs/{design_id}/entities",
    response_model=List[DatabaseEntityRead],
    summary="List all entities in a database design",
)
async def list_entities(
    design_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[DatabaseEntityRead]:
    await _require_design(design_id, svc)
    return [DatabaseEntityRead.model_validate(e) for e in await svc.list_entities(design_id)]


# ── GET /database/designs/{design_id}/relationships ──────────────────────

@router.get(
    "/designs/{design_id}/relationships",
    response_model=List[DatabaseRelationshipRead],
    summary="List entity relationships in a database design",
)
async def list_relationships(
    design_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[DatabaseRelationshipRead]:
    await _require_design(design_id, svc)
    return [
        DatabaseRelationshipRead.model_validate(r)
        for r in await svc.list_relationships(design_id)
    ]


# ── GET /database/designs/{design_id}/indexes ────────────────────────────

@router.get(
    "/designs/{design_id}/indexes",
    response_model=List[DatabaseIndexRead],
    summary="List index recommendations for a database design",
)
async def list_indexes(
    design_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[DatabaseIndexRead]:
    await _require_design(design_id, svc)
    return [DatabaseIndexRead.model_validate(i) for i in await svc.list_indexes(design_id)]


# ── GET /database/designs/{design_id}/migrations ─────────────────────────

@router.get(
    "/designs/{design_id}/migrations",
    response_model=List[MigrationPlanRead],
    summary="Get Alembic migration plans for a database design",
)
async def list_migrations(
    design_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[MigrationPlanRead]:
    await _require_design(design_id, svc)
    return [MigrationPlanRead.model_validate(m) for m in await svc.list_migrations(design_id)]


# ── GET /database/designs/{design_id}/optimizations ─────────────────────

@router.get(
    "/designs/{design_id}/optimizations",
    response_model=List[QueryOptimizationReportRead],
    summary="Get query optimization recommendations for a database design",
)
async def list_optimizations(
    design_id: uuid.UUID,
    priority: Optional[str] = Query(None, description="Filter by priority: HIGH, MEDIUM, LOW"),
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> List[QueryOptimizationReportRead]:
    await _require_design(design_id, svc)
    return [
        QueryOptimizationReportRead.model_validate(o)
        for o in await svc.list_optimizations(design_id, priority=priority)
    ]


# ── POST /database/designs/{design_id}/regenerate ────────────────────────

@router.post(
    "/designs/{design_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger regeneration of a database design",
)
async def regenerate_design(
    design_id: uuid.UUID,
    body: RegenerateRequest,
    _: TokenData = Depends(get_current_user),
    svc: DatabaseDesignService = Depends(get_database_design_service),
) -> dict:
    design = await _require_design(design_id, svc)
    await svc.trigger_regeneration(
        design_id=design_id,
        workflow_id=design.workflow_id,
        reason=body.reason,
    )
    return {
        "success": True,
        "data": {
            "design_id": str(design_id),
            "message": "Regeneration triggered. The agent will produce a new design shortly.",
        },
        "error": None,
    }
