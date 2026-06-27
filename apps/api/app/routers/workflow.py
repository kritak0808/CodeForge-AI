import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.schemas.workflow import WorkflowCreate, WorkflowResponse, WorkflowDetailsResponse, ApprovalDecision, ApprovalResponse
from app.services.workflow import WorkflowService
from app.dependencies import get_workflow_service, get_current_user, get_db
from app.schemas.token import TokenData
from app.models import Workflow

router = APIRouter(prefix="/workflows", tags=["Workflows"])

# Helper request schemas
class CommentsPayload(BaseModel):
    comments: Optional[str] = None


# ── GET /workflows ──────────────────────────────────────────────────────────
@router.get("")
async def list_workflows(
    project_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List workflows, optionally filtered by project_id."""
    q = select(Workflow).offset(skip).limit(limit).order_by(Workflow.created_at.desc())
    if project_id:
        q = q.where(Workflow.project_id == project_id)
    result = await db.execute(q)
    workflows = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "workflow_id":     str(w.workflow_id),
                "project_id":      str(w.project_id),
                "current_state":   w.current_state,
                "status":          w.status,
                "tasks_completed": w.tasks_completed,
                "tasks_total":     w.tasks_total,
                "triggered_by":    str(w.triggered_by) if w.triggered_by else None,
                "created_at":      w.created_at.isoformat(),
                "updated_at":      w.updated_at.isoformat(),
            }
            for w in workflows
        ],
        "error": None,
    }

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def trigger_workflow(
    payload: WorkflowCreate,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Triggers/Initiates a new agent execution workflow thread.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    workflow = await service.trigger_workflow(payload.project_id, payload.requirements, user_id)

    return {
        "success": True,
        "data": {
            "workflow_id":     str(workflow.workflow_id),
            "project_id":      str(workflow.project_id),
            "current_state":   workflow.current_state,
            "status":          workflow.status,
            "tasks_completed": workflow.tasks_completed,
            "tasks_total":     workflow.tasks_total,
            "triggered_by":    str(workflow.triggered_by),
            "created_at":      workflow.created_at.isoformat(),
            "updated_at":      workflow.updated_at.isoformat(),
        },
        "error": None
    }

@router.get("/{workflow_id}", response_model=dict)
async def get_workflow_by_id(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves workflow status details.
    """
    workflow = await service.get_workflow_details(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )

    data = {
        "workflow_id": str(workflow.workflow_id),
        "project_id": str(workflow.project_id),
        "current_state": workflow.current_state,
        "status": workflow.status,
        "tasks_completed": workflow.tasks_completed,
        "tasks_total": workflow.tasks_total,
        "triggered_by": str(workflow.triggered_by) if workflow.triggered_by else None,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
        "states": [
            {
                "state_id": str(s.state_id),
                "state": s.state,
                "metadata_json": s.metadata_json,
                "entered_at": s.entered_at.isoformat(),
                "exited_at": s.exited_at.isoformat() if s.exited_at else None
            }
            for s in workflow.states
        ],
        "tasks": [
            {
                "task_id": str(t.task_id),
                "agent_id": t.agent_id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "depends_on": t.depends_on,
                "assigned_at": t.assigned_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in workflow.tasks
        ],
        "approvals": [
            {
                "approval_id": str(a.approval_id),
                "approval_type": a.approval_type,
                "status": a.status,
                "artifact_payload": a.artifact_payload,
                "comments": a.comments,
                "created_at": a.created_at.isoformat(),
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "approver_id": str(a.approver_id) if a.approver_id else None
            }
            for a in workflow.approvals
        ],
        "metrics": [
            {
                "metric_id": str(m.metric_id),
                "agent_id": m.agent_id,
                "tokens_consumed": m.tokens_consumed,
                "cost_usd": float(m.cost_usd),
                "latency_ms": m.latency_ms,
                "recorded_at": m.recorded_at.isoformat()
            }
            for m in workflow.metrics
        ]
    }

    return {
        "success": True,
        "data": data,
        "error": None
    }

@router.get("/{workflow_id}/status", response_model=dict)
async def get_workflow_status(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves full execution details, state parameters, approvals list, and tasks logs (backward compatibility).
    """
    return await get_workflow_by_id(workflow_id, current_user, service)

@router.post("/{workflow_id}/pause", response_model=dict)
async def pause_workflow(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Pauses a workflow execution run.
    """
    workflow = await service.pause_workflow(workflow_id)
    return {
        "success": True,
        "data": {
            "workflow_id": str(workflow.workflow_id),
            "current_state": workflow.current_state,
            "updated_at": workflow.updated_at.isoformat()
        },
        "error": None
    }

@router.post("/{workflow_id}/resume", response_model=dict)
async def resume_workflow(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Resumes a paused workflow execution run.
    """
    workflow = await service.resume_workflow(workflow_id)
    return {
        "success": True,
        "data": {
            "workflow_id": str(workflow.workflow_id),
            "current_state": workflow.current_state,
            "updated_at": workflow.updated_at.isoformat()
        },
        "error": None
    }

@router.post("/{workflow_id}/cancel", response_model=dict)
async def cancel_workflow(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Cancels a workflow execution run.
    """
    workflow = await service.cancel_workflow(workflow_id)
    return {
        "success": True,
        "data": {
            "workflow_id": str(workflow.workflow_id),
            "current_state": workflow.current_state,
            "updated_at": workflow.updated_at.isoformat()
        },
        "error": None
    }

@router.get("/{workflow_id}/state", response_model=dict)
async def get_workflow_state(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves only the metadata state details of a workflow.
    """
    state_details = await service.get_workflow_state(workflow_id)
    return {
        "success": True,
        "data": state_details,
        "error": None
    }

@router.get("/{workflow_id}/logs", response_model=dict)
async def get_workflow_logs(
    workflow_id: uuid.UUID,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves detailed execution trace logs.
    """
    logs = await service.get_workflow_logs(workflow_id)
    return {
        "success": True,
        "data": logs,
        "error": None
    }

@router.post("/{workflow_id}/approve", response_model=dict)
async def approve_workflow_step(
    workflow_id: uuid.UUID,
    payload: CommentsPayload,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Approves the pending human validation step.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    approval = await service.approve_workflow_step(workflow_id, user_id, payload.comments)
    return {
        "success": True,
        "data": {
            "approval_id": str(approval.approval_id),
            "workflow_id": str(approval.workflow_id),
            "status": approval.status,
            "comments": approval.comments,
            "decided_at": approval.decided_at.isoformat()
        },
        "error": None
    }

@router.post("/{workflow_id}/reject", response_model=dict)
async def reject_workflow_step(
    workflow_id: uuid.UUID,
    payload: CommentsPayload,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Rejects the pending human validation step.
    """
    user_id = uuid.UUID(current_user.scopes[0])
    approval = await service.reject_workflow_step(workflow_id, user_id, payload.comments)
    return {
        "success": True,
        "data": {
            "approval_id": str(approval.approval_id),
            "workflow_id": str(approval.workflow_id),
            "status": approval.status,
            "comments": approval.comments,
            "decided_at": approval.decided_at.isoformat()
        },
        "error": None
    }

@router.post("/approvals/{approval_id}/decision", response_model=dict)
async def submit_approval_decision(
    approval_id: uuid.UUID,
    payload: ApprovalDecision,
    current_user: TokenData = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Submits a decision matching a pending human-in-the-loop validation barrier (backward compatibility).
    """
    user_id = uuid.UUID(current_user.scopes[0])
    approval = await service.submit_approval_decision(approval_id, payload, user_id)
    
    return {
        "success": True,
        "data": {
            "approval_id": str(approval.approval_id),
            "workflow_id": str(approval.workflow_id),
            "status": approval.status,
            "comments": approval.comments,
            "decided_at": approval.decided_at.isoformat()
        },
        "error": None
    }
