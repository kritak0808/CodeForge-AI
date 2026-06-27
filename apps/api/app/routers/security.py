"""
REST router for the Security Agent – Milestone 11.
Prefix: /api/v1/security
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_security_generation_service
from app.schemas.token import TokenData
from app.schemas.security import (
    SecurityGenerationSummary,
    SecurityGenerationRead,
    SecurityGenerationFullResponse,
    ThreatModelRead,
    SecurityFindingRead,
    DependencyScanRead,
    SecretScanRead,
    RbacAuditRead,
    SecurityReportRead,
    GenerateSecurityRequest,
    RegenerateSecurityRequest,
)
from app.services.security import SecurityGenerationService

router = APIRouter(prefix="/security", tags=["Security Agent"])


# ── POST /security/generate ──────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Security threat modeling and scans for a workflow",
)
async def generate_security(
    body: GenerateSecurityRequest,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
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
                "Security generation started. "
                "Poll GET /security/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /security/generations/{generation_id} ─────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=SecurityGenerationFullResponse,
    summary="Get full Security generation with all threat modeling and scans",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> SecurityGenerationFullResponse:
    gen = await svc.get_full_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityGeneration '{generation_id}' not found",
        )

    tms = await svc.list_threat_models(generation_id)
    findings = await svc.list_security_findings(generation_id)
    deps = await svc.list_dependency_scans(generation_id)
    secrets = await svc.list_secret_scans(generation_id)
    rbacs = await svc.list_rbac_audits(generation_id)
    reps = await svc.list_security_reports(generation_id)

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
        "threat_models": tms,
        "security_findings": findings,
        "dependency_scans": deps,
        "secret_scans": secrets,
        "rbac_audits": rbacs,
        "security_reports": reps,
    }
    return SecurityGenerationFullResponse.model_validate(res_dict)


# ── GET /security/threat-models/{model_id} ────────────────────────────────────

@router.get(
    "/threat-models/{model_id}",
    response_model=ThreatModelRead,
    summary="Get threat model by ID",
)
async def get_threat_model(
    model_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> ThreatModelRead:
    tm = await svc.threat_model_repo.get(model_id)
    if not tm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ThreatModel '{model_id}' not found",
        )
    return ThreatModelRead.model_validate(tm)


# ── GET /security/findings/{finding_id} ───────────────────────────────────────

@router.get(
    "/findings/{finding_id}",
    response_model=SecurityFindingRead,
    summary="Get security finding by ID",
)
async def get_security_finding(
    finding_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> SecurityFindingRead:
    sf = await svc.finding_repo.get(finding_id)
    if not sf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityFinding '{finding_id}' not found",
        )
    return SecurityFindingRead.model_validate(sf)


# ── GET /security/dependency-scans/{scan_id} ──────────────────────────────────

@router.get(
    "/dependency-scans/{scan_id}",
    response_model=DependencyScanRead,
    summary="Get dependency scan result by ID",
)
async def get_dependency_scan(
    scan_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> DependencyScanRead:
    ds = await svc.dependency_repo.get(scan_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DependencyScan '{scan_id}' not found",
        )
    return DependencyScanRead.model_validate(ds)


# ── GET /security/secret-scans/{scan_id} ──────────────────────────────────────

@router.get(
    "/secret-scans/{scan_id}",
    response_model=SecretScanRead,
    summary="Get secret scan result by ID",
)
async def get_secret_scan(
    scan_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> SecretScanRead:
    ss = await svc.secret_repo.get(scan_id)
    if not ss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecretScan '{scan_id}' not found",
        )
    return SecretScanRead.model_validate(ss)


# ── GET /security/rbac-audits/{audit_id} ──────────────────────────────────────

@router.get(
    "/rbac-audits/{audit_id}",
    response_model=RbacAuditRead,
    summary="Get RBAC audit by ID",
)
async def get_rbac_audit(
    audit_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> RbacAuditRead:
    ra = await svc.rbac_repo.get(audit_id)
    if not ra:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RbacAudit '{audit_id}' not found",
        )
    return RbacAuditRead.model_validate(ra)


# ── GET /security/reports/{report_id} ─────────────────────────────────────────

@router.get(
    "/reports/{report_id}",
    response_model=SecurityReportRead,
    summary="Get compiled security report by ID",
)
async def get_security_report(
    report_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> SecurityReportRead:
    sr = await svc.report_repo.get(report_id)
    if not sr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityReport '{report_id}' not found",
        )
    return SecurityReportRead.model_validate(sr)


# ── POST /security/generations/{generation_id}/regenerate ─────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Security generation and scanning regeneration",
)
async def regenerate_security(
    generation_id: uuid.UUID,
    body: RegenerateSecurityRequest,
    _: TokenData = Depends(get_current_user),
    svc: SecurityGenerationService = Depends(get_security_generation_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityGeneration '{generation_id}' not found",
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
            "message": "Security regeneration triggered. The agent will run threat modeling and produce new report shortly.",
        },
        "error": None,
    }
