"""
REST router for the Observability & Monitoring Platform – Milestone 15.
Prefix: /api/v1/observability
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_observability_service
from app.schemas.token import TokenData
from app.schemas.observability import (
    ObservabilityGenerationFullResponse,
    AgentMetricRead,
    WorkflowMetricRead,
    ApiMetricRead,
    SystemMetricRead,
    ErrorEventRead,
    AlertRuleRead,
    AlertEventRead,
    GenerateObservabilityRequest,
    RegenerateObservabilityRequest,
)
from app.services.observability import ObservabilityService

router = APIRouter(prefix="/observability", tags=["Observability Agent"])


# ── GET /observability/agents ─────────────────────────────────────────────────
@router.get("/agents", summary="List all agent health records")
async def list_agent_health(
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> dict:
    """Return the latest health heartbeat for every known agent type."""
    from app.models import AgentHealth
    from sqlalchemy import select
    from app.database import get_db
    from fastapi import Depends as _Depends
    # Use the service's session
    try:
        result = await svc.repository.db.execute(select(AgentHealth))
        agents = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "agent_id":       str(a.agent_health_id),
                    "agent_type":     a.agent_type,
                    "status":         a.status,
                    "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else "",
                    "tasks_completed": a.tasks_completed or 0,
                    "tasks_failed":   a.tasks_failed or 0,
                    "avg_duration_ms": float(a.avg_response_time_ms or 0),
                }
                for a in agents
            ],
            "error": None,
        }
    except Exception as exc:
        # Return empty list if table doesn't exist yet
        return {"success": True, "data": [], "error": None}


# ── GET /observability/metrics ────────────────────────────────────────────────
@router.get("/metrics", summary="Platform-level aggregate metrics")
async def get_metrics(
    _: TokenData = Depends(get_current_user),
) -> dict:
    return {
        "success": True,
        "data": {
            "note": "Connect Prometheus scraper to /metrics for live telemetry"
        },
        "error": None,
    }


# ── POST /observability/generate ─────────────────────────────────────────────

@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an observability snapshot generation for a project workflow",
)
async def generate_observability(
    body: GenerateObservabilityRequest,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
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
                "Observability generation started. "
                "Poll GET /observability/generations/{id} for status."
            ),
        },
        "error": None,
    }


# ── GET /observability/generations/{generation_id} ────────────────────────────

@router.get(
    "/generations/{generation_id}",
    response_model=ObservabilityGenerationFullResponse,
    summary="Get full observability generation with all child metrics and events",
)
async def get_generation(
    generation_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> ObservabilityGenerationFullResponse:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ObservabilityGeneration '{generation_id}' not found",
        )

    agent_metrics = await svc.list_agent_metrics(generation_id)
    workflow_metrics = await svc.list_workflow_metrics(generation_id)
    api_metrics = await svc.list_api_metrics(generation_id)
    system_metrics = await svc.list_system_metrics(generation_id)
    error_events = await svc.list_error_events(generation_id)
    alert_rules = await svc.list_alert_rules(generation_id)
    alert_events = await svc.list_alert_events(generation_id)

    return ObservabilityGenerationFullResponse.model_validate({
        "generation_id": gen.generation_id,
        "project_id": gen.project_id,
        "workflow_id": gen.workflow_id,
        "status": gen.status,
        "notes": gen.notes,
        "created_at": gen.created_at,
        "updated_at": gen.updated_at,
        "agent_metrics": agent_metrics,
        "workflow_metrics": workflow_metrics,
        "api_metrics": api_metrics,
        "system_metrics": system_metrics,
        "error_events": error_events,
        "alert_rules": alert_rules,
        "alert_events": alert_events,
    })


# ── GET /observability/agent-metrics/{metric_id} ──────────────────────────────

@router.get(
    "/agent-metrics/{metric_id}",
    response_model=AgentMetricRead,
    summary="Get a single agent metric record by ID",
)
async def get_agent_metric(
    metric_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> AgentMetricRead:
    metric = await svc.agent_metric_repo.get(metric_id)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AgentMetric '{metric_id}' not found",
        )
    return AgentMetricRead.model_validate(metric)


# ── GET /observability/workflow-metrics/{metric_id} ───────────────────────────

@router.get(
    "/workflow-metrics/{metric_id}",
    response_model=WorkflowMetricRead,
    summary="Get a single workflow metric record by ID",
)
async def get_workflow_metric(
    metric_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> WorkflowMetricRead:
    metric = await svc.workflow_metric_repo.get(metric_id)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkflowMetric '{metric_id}' not found",
        )
    return WorkflowMetricRead.model_validate(metric)


# ── GET /observability/api-metrics/{metric_id} ───────────────────────────────

@router.get(
    "/api-metrics/{metric_id}",
    response_model=ApiMetricRead,
    summary="Get a single API metric record by ID",
)
async def get_api_metric(
    metric_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> ApiMetricRead:
    metric = await svc.api_metric_repo.get(metric_id)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ApiMetric '{metric_id}' not found",
        )
    return ApiMetricRead.model_validate(metric)


# ── GET /observability/system-metrics/{metric_id} ────────────────────────────

@router.get(
    "/system-metrics/{metric_id}",
    response_model=SystemMetricRead,
    summary="Get a single system metric snapshot by ID",
)
async def get_system_metric(
    metric_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> SystemMetricRead:
    metric = await svc.system_metric_repo.get(metric_id)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SystemMetric '{metric_id}' not found",
        )
    return SystemMetricRead.model_validate(metric)


# ── GET /observability/error-events/{event_id} ───────────────────────────────

@router.get(
    "/error-events/{event_id}",
    response_model=ErrorEventRead,
    summary="Get a single structured error event by ID",
)
async def get_error_event(
    event_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> ErrorEventRead:
    event = await svc.error_event_repo.get(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ErrorEvent '{event_id}' not found",
        )
    return ErrorEventRead.model_validate(event)


# ── GET /observability/alert-rules/{rule_id} ─────────────────────────────────

@router.get(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleRead,
    summary="Get a single alert rule definition by ID",
)
async def get_alert_rule(
    rule_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> AlertRuleRead:
    rule = await svc.alert_rule_repo.get(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AlertRule '{rule_id}' not found",
        )
    return AlertRuleRead.model_validate(rule)


# ── GET /observability/alert-events/{alert_id} ───────────────────────────────

@router.get(
    "/alert-events/{alert_id}",
    response_model=AlertEventRead,
    summary="Get a single fired alert event by ID",
)
async def get_alert_event(
    alert_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> AlertEventRead:
    alert = await svc.alert_event_repo.get(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AlertEvent '{alert_id}' not found",
        )
    return AlertEventRead.model_validate(alert)


# ── POST /observability/generations/{generation_id}/regenerate ────────────────

@router.post(
    "/generations/{generation_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger observability regeneration for an existing generation",
)
async def regenerate_observability(
    generation_id: uuid.UUID,
    body: RegenerateObservabilityRequest,
    _: TokenData = Depends(get_current_user),
    svc: ObservabilityService = Depends(get_observability_service),
) -> dict:
    gen = await svc.get_generation(generation_id)
    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ObservabilityGeneration '{generation_id}' not found",
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
            "message": "Observability regeneration triggered. A new snapshot will be collected shortly.",
        },
        "error": None,
    }
