"""
REST router for the Autonomous SDLC Controller – Milestone 17.
Prefix: /api/v1/controller
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_autonomous_controller_service
from app.schemas.token import TokenData
from app.schemas.controller import (
    StartControllerRequest,
    PauseControllerRequest,
    ResumeControllerRequest,
    RetryControllerRequest,
    RollbackControllerRequest,
    CancelControllerRequest,
    AutonomousControllerRead,
    AutonomousControllerFullResponse,
    WorkflowDecisionRead,
    AgentHealthRead,
)
from app.services.controller import AutonomousControllerService

router = APIRouter(prefix="/controller", tags=["Autonomous SDLC Controller"])


@router.post(
    "/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start autonomous controller run",
)
async def start_controller(
    body: StartControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.trigger_controller(project_id=body.project_id, workflow_id=body.workflow_id)
    return {
        "success": True,
        "data": {
            "controller_id": str(ctrl.controller_id),
            "status": ctrl.status,
        },
    }


@router.post(
    "/pause",
    summary="Pause active controller execution",
)
async def pause_controller(
    body: PauseControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.pause_execution(body.workflow_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active controller not found for workflow '{body.workflow_id}'",
        )
    return {
        "success": True,
        "data": {
            "status": ctrl.status,
        },
    }


@router.post(
    "/resume",
    summary="Resume paused controller execution",
)
async def resume_controller(
    body: ResumeControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.resume_execution(body.workflow_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller not found for workflow '{body.workflow_id}'",
        )
    return {
        "success": True,
        "data": {
            "status": ctrl.status,
        },
    }


@router.post(
    "/retry",
    summary="Trigger a manual or controller-initiated retry",
)
async def retry_controller(
    body: RetryControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.retry_step(body.workflow_id, body.step)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller not found for workflow '{body.workflow_id}'",
        )
    return {
        "success": True,
        "data": {
            "action": "RETRY",
            "step": body.step,
        },
    }


@router.post(
    "/rollback",
    summary="Trigger a rollback to a target step",
)
async def rollback_controller(
    body: RollbackControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.rollback_step(body.workflow_id, body.target_step, body.reason)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller not found for workflow '{body.workflow_id}'",
        )
    return {
        "success": True,
        "data": {
            "action": "ROLLBACK",
            "target_step": body.target_step,
        },
    }


@router.post(
    "/cancel",
    summary="Manually cancel execution run",
)
async def cancel_controller(
    body: CancelControllerRequest,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> dict:
    ctrl = await svc.cancel_execution(body.workflow_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller not found for workflow '{body.workflow_id}'",
        )
    return {
        "success": True,
        "data": {
            "status": ctrl.status,
        },
    }


@router.get(
    "/status/{workflow_id}",
    response_model=AutonomousControllerFullResponse,
    summary="Get full controller status and history logs for a workflow",
)
async def get_controller_status(
    workflow_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> AutonomousControllerFullResponse:
    ctrl = await svc.get_by_workflow(workflow_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller context for workflow '{workflow_id}' not found",
        )

    decisions = await svc.list_decisions(ctrl.controller_id)
    retries = await svc.list_retries(ctrl.controller_id)
    failures = await svc.list_failures(ctrl.controller_id)
    rollbacks = await svc.list_rollbacks(ctrl.controller_id)
    plan = await svc.get_plan(ctrl.controller_id)
    logs = await svc.list_logs(ctrl.controller_id)

    return AutonomousControllerFullResponse.model_validate({
        "controller_id": ctrl.controller_id,
        "project_id": ctrl.project_id,
        "workflow_id": ctrl.workflow_id,
        "status": ctrl.status,
        "current_step": ctrl.current_step,
        "budget_limit": ctrl.budget_limit,
        "created_at": ctrl.created_at,
        "updated_at": ctrl.updated_at,
        "decisions": decisions,
        "retries": retries,
        "failures": failures,
        "rollbacks": rollbacks,
        "execution_plans": [plan] if plan else [],
        "logs": logs,
    })


@router.get(
    "/decisions/{workflow_id}",
    response_model=List[WorkflowDecisionRead],
    summary="Get controller decisions for a workflow",
)
async def get_decisions(
    workflow_id: uuid.UUID,
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> List[WorkflowDecisionRead]:
    ctrl = await svc.get_by_workflow(workflow_id)
    if not ctrl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Controller context not found for workflow '{workflow_id}'",
        )
    return await svc.list_decisions(ctrl.controller_id)


@router.get(
    "/health",
    response_model=List[AgentHealthRead],
    summary="Get health status metrics for all SDLC agents",
)
async def get_health(
    _: TokenData = Depends(get_current_user),
    svc: AutonomousControllerService = Depends(get_autonomous_controller_service),
) -> List[AgentHealthRead]:
    return await svc.list_agent_health()
