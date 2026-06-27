"""
REST router for the Cost Optimization Agent – Milestone 16.
Prefix: /api/v1/cost
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_cost_optimization_service
from app.schemas.token import TokenData
from app.schemas.cost import (
    CostGenerationFullResponse,
    CostReportRead,
    ResourceUsageMetricRead,
    OptimizationRecommendationRead,
    SavingsEstimateRead,
    BudgetPolicyRead,
    CostAlertRead,
    GenerateCostRequest,
    RegenerateCostRequest,
    BudgetPolicyRequest,
)
from app.services.cost import CostOptimizationService

router = APIRouter(prefix="/cost", tags=["Cost Optimization Agent"])


# ── GET /cost/report ──────────────────────────────────────────────────────────
@router.get("/report", summary="Aggregate cost report for the platform or a project")
async def get_cost_report(
    project_id: str | None = None,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> dict:
    """Aggregate cost totals from stored CostReport records."""
    from app.models import CostReport
    from sqlalchemy import select, func as sqlfunc
    import uuid as _uuid

    try:
        q = select(CostReport)
        if project_id:
            q = q.where(CostReport.project_id == _uuid.UUID(project_id))
        result = await svc.repository.db.execute(q)
        reports = result.scalars().all()

        total_cost    = sum(float(r.total_cost_usd or 0) for r in reports)
        token_cost    = sum(float(r.llm_cost_usd or 0) for r in reports)
        compute_cost  = sum(float(r.compute_cost_usd or 0) for r in reports)
        storage_cost  = sum(float(r.storage_cost_usd or 0) for r in reports)
        total_tokens  = sum(int(r.total_tokens or 0) for r in reports)
        input_tokens  = sum(int(r.input_tokens or 0) for r in reports)
        output_tokens = sum(int(r.output_tokens or 0) for r in reports)

        breakdown = []
        if total_cost > 0:
            for label, amount in [
                ("LLM Tokens", token_cost),
                ("Compute (K8s)", compute_cost),
                ("Storage", storage_cost),
            ]:
                breakdown.append({
                    "category":   label,
                    "amount":     round(amount, 4),
                    "percentage": round((amount / total_cost) * 100, 1),
                })

        return {
            "success": True,
            "data": {
                "total_cost_usd":   round(total_cost, 4),
                "token_cost_usd":   round(token_cost, 4),
                "compute_cost_usd": round(compute_cost, 4),
                "storage_cost_usd": round(storage_cost, 4),
                "total_tokens":     total_tokens,
                "input_tokens":     input_tokens,
                "output_tokens":    output_tokens,
                "breakdown":        breakdown,
            },
            "error": None,
        }
    except Exception:
        return {
            "success": True,
            "data": {
                "total_cost_usd": 0, "token_cost_usd": 0,
                "compute_cost_usd": 0, "storage_cost_usd": 0,
                "total_tokens": 0, "input_tokens": 0, "output_tokens": 0,
                "breakdown": [],
            },
            "error": None,
        }


# ── POST /cost/generate ───────────────────────────────────────────────────────


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a cost optimization analysis for a project workflow",
)
async def generate_cost_analysis(
    body: GenerateCostRequest,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> dict:
    gen = await svc.trigger_generation(
        project_id=body.project_id,
        workflow_id=body.workflow_id,
    )
    return {
        "success": True,
        "data": {
            "generation_id": str(gen.generation_id),
            "status": gen.status,
            "message": (
                "Cost optimization analysis started. "
                "Poll GET /cost/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /cost/generations/{generation_id} ─────────────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=CostGenerationFullResponse,
    summary="Get full cost generation with all child reports, metrics, and recommendations",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> CostGenerationFullResponse:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CostGeneration '{generation_id}' not found",
        )

    reports = await svc.list_reports(generation_id)
    metrics = await svc.list_metrics(generation_id)
    recommendations = await svc.list_recommendations(generation_id)
    savings = await svc.list_savings(generation_id)
    alerts = await svc.list_alerts(generation_id)

    return CostGenerationFullResponse.model_validate({
        "generation_id": gen.generation_id,
        "project_id": gen.project_id,
        "workflow_id": gen.workflow_id,
        "status": gen.status,
        "total_cost": gen.total_cost,
        "estimated_monthly_cost": gen.estimated_monthly_cost,
        "currency": gen.currency,
        "created_at": gen.created_at,
        "updated_at": gen.updated_at,
        "cost_reports": reports,
        "resource_usage_metrics": metrics,
        "optimization_recommendations": recommendations,
        "savings_estimates": savings,
        "cost_alerts": alerts,
    })


# ── GET /cost/reports/{report_id} ─────────────────────────────────────────────

@router.get(
    "/reports/{report_id}",
    response_model=CostReportRead,
    summary="Get a single cost report by ID",
)
async def get_report(
    report_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> CostReportRead:
    report = await svc.report_repo.get(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CostReport '{report_id}' not found",
        )
    return CostReportRead.model_validate(report)


# ── GET /cost/metrics/{metric_id} ─────────────────────────────────────────────

@router.get(
    "/metrics/{metric_id}",
    response_model=ResourceUsageMetricRead,
    summary="Get a single resource usage metric by ID",
)
async def get_metric(
    metric_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> ResourceUsageMetricRead:
    metric = await svc.metric_repo.get(metric_id)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ResourceUsageMetric '{metric_id}' not found",
        )
    return ResourceUsageMetricRead.model_validate(metric)


# ── GET /cost/recommendations/{recommendation_id} ─────────────────────────────

@router.get(
    "/recommendations/{recommendation_id}",
    response_model=OptimizationRecommendationRead,
    summary="Get a single optimization recommendation by ID",
)
async def get_recommendation(
    recommendation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> OptimizationRecommendationRead:
    rec = await svc.recommendation_repo.get(recommendation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OptimizationRecommendation '{recommendation_id}' not found",
        )
    return OptimizationRecommendationRead.model_validate(rec)


# ── GET /cost/savings/{estimate_id} ──────────────────────────────────────────

@router.get(
    "/savings/{estimate_id}",
    response_model=SavingsEstimateRead,
    summary="Get a single savings estimate by ID",
)
async def get_savings(
    estimate_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> SavingsEstimateRead:
    est = await svc.savings_repo.get(estimate_id)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SavingsEstimate '{estimate_id}' not found",
        )
    return SavingsEstimateRead.model_validate(est)


# ── GET /cost/alerts/{alert_id} ───────────────────────────────────────────────

@router.get(
    "/alerts/{alert_id}",
    response_model=CostAlertRead,
    summary="Get a single cost alert by ID",
)
async def get_alert(
    alert_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> CostAlertRead:
    alert = await svc.alert_repo.get(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CostAlert '{alert_id}' not found",
        )
    return CostAlertRead.model_validate(alert)


# ── GET /cost/budget-policies/{project_id} ────────────────────────────────────

@router.get(
    "/budget-policies/{project_id}",
    response_model=BudgetPolicyRead,
    summary="Get the active budget policy for a project",
)
async def get_budget_policy(
    project_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> BudgetPolicyRead:
    policy = await svc.get_budget_policy(project_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active BudgetPolicy found for project '{project_id}'",
        )
    return BudgetPolicyRead.model_validate(policy)


# ── POST /cost/budget-policies ────────────────────────────────────────────────

@router.post(
    "/budget-policies",
    response_model=BudgetPolicyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update the budget policy for a project",
)
async def upsert_budget_policy(
    body: BudgetPolicyRequest,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> BudgetPolicyRead:
    policy = await svc.upsert_budget_policy(body)
    return BudgetPolicyRead.model_validate(policy)


# ── POST /cost/generations/{generation_id}/regenerate ─────────────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger cost optimization regeneration for an existing generation",
)
async def regenerate_cost_analysis(
    generation_id: uuid.UUID,
    body: RegenerateCostRequest,
    _: TokenData = Depends(get_current_user),
    svc: CostOptimizationService = Depends(get_cost_optimization_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CostGeneration '{generation_id}' not found",
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
            "message": "Cost optimization regeneration triggered.",
        },
        "error": None,
    }
