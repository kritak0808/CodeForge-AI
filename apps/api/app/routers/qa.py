"""
REST router for the QA Agent – Milestone 10.
Prefix: /api/v1/qa
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_qa_generation_service
from app.schemas.token import TokenData
from app.schemas.qa import (
    QaGenerationSummary,
    QaGenerationRead,
    QaGenerationFullResponse,
    QaTestSuiteRead,
    QaTestCaseRead,
    QaTestRunRead,
    QaBugReportRead,
    QaCoverageReportRead,
    QaQualityMetricsRead,
    GenerateQaRequest,
    RegenerateQaRequest,
)
from app.services.qa import QaGenerationService

router = APIRouter(prefix="/qa", tags=["QA Agent"])


# ── POST /qa/generate ─────────────────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger QA test generation and analysis for a workflow",
)
async def generate_qa(
    body: GenerateQaRequest,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
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
                "QA generation started. "
                "Poll GET /qa/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /qa/generations/{generation_id} ────────────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=QaGenerationFullResponse,
    summary="Get full QA generation with all test artifacts",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaGenerationFullResponse:
    gen = await svc.get_full_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaGeneration '{generation_id}' not found",
        )

    suites = await svc.list_test_suites(generation_id)
    cases = await svc.list_test_cases(generation_id)
    runs = await svc.list_test_runs(generation_id)
    bugs = await svc.list_bug_reports(generation_id)
    coverages = await svc.list_coverage_reports(generation_id)
    metrics = await svc.list_quality_metrics(generation_id)

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
        "test_suites": suites,
        "test_cases": cases,
        "test_runs": runs,
        "bug_reports": bugs,
        "coverage_reports": coverages,
        "quality_metrics": metrics,
    }
    return QaGenerationFullResponse.model_validate(res_dict)


# ── GET /qa/test-suites/{suite_id} ────────────────────────────────────────────

@router.get(
    "/test-suites/{suite_id}",
    response_model=QaTestSuiteRead,
    summary="Get generated QA test suite by ID",
)
async def get_test_suite(
    suite_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaTestSuiteRead:
    suite = await svc.suite_repo.get(suite_id)
    if not suite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaTestSuite '{suite_id}' not found",
        )
    return QaTestSuiteRead.model_validate(suite)


# ── GET /qa/test-cases/{case_id} ──────────────────────────────────────────────

@router.get(
    "/test-cases/{case_id}",
    response_model=QaTestCaseRead,
    summary="Get generated test case details by ID",
)
async def get_test_case(
    case_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaTestCaseRead:
    case = await svc.case_repo.get(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaTestCase '{case_id}' not found",
        )
    return QaTestCaseRead.model_validate(case)


# ── GET /qa/test-runs/{run_id} ────────────────────────────────────────────────

@router.get(
    "/test-runs/{run_id}",
    response_model=QaTestRunRead,
    summary="Get QA test run report log by ID",
)
async def get_test_run(
    run_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaTestRunRead:
    run = await svc.run_repo.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaTestRun '{run_id}' not found",
        )
    return QaTestRunRead.model_validate(run)


# ── GET /qa/bug-reports/{bug_id} ──────────────────────────────────────────────

@router.get(
    "/bug-reports/{bug_id}",
    response_model=QaBugReportRead,
    summary="Get documented bug report by ID",
)
async def get_bug_report(
    bug_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaBugReportRead:
    bug = await svc.bug_repo.get(bug_id)
    if not bug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaBugReport '{bug_id}' not found",
        )
    return QaBugReportRead.model_validate(bug)


# ── GET /qa/coverage-reports/{report_id} ──────────────────────────────────────

@router.get(
    "/coverage-reports/{report_id}",
    response_model=QaCoverageReportRead,
    summary="Get coverage report by ID",
)
async def get_coverage_report(
    report_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaCoverageReportRead:
    rep = await svc.coverage_repo.get(report_id)
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaCoverageReport '{report_id}' not found",
        )
    return QaCoverageReportRead.model_validate(rep)


# ── GET /qa/quality-metrics/{metrics_id} ──────────────────────────────────────

@router.get(
    "/quality-metrics/{metrics_id}",
    response_model=QaQualityMetricsRead,
    summary="Get quality metrics scorecard by ID",
)
async def get_quality_metrics(
    metrics_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> QaQualityMetricsRead:
    met = await svc.metrics_repo.get(metrics_id)
    if not met:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaQualityMetrics '{metrics_id}' not found",
        )
    return QaQualityMetricsRead.model_validate(met)


# ── POST /qa/generations/{generation_id}/regenerate ───────────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger QA suite regeneration",
)
async def regenerate_qa(
    generation_id: uuid.UUID,
    body: RegenerateQaRequest,
    _: TokenData = Depends(get_current_user),
    svc: QaGenerationService = Depends(get_qa_generation_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QaGeneration '{generation_id}' not found",
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
            "message": "QA regeneration triggered. The agent will run tests and produce new code shortly.",
        },
        "error": None,
    }
