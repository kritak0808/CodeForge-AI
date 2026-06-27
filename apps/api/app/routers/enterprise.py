from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.dependencies import get_current_user, get_api_key_service, get_audit_service, get_flag_service
from app.authz import PermissionRequired
from app.services.enterprise import ApiKeyService, AuditService, FeatureFlagService
from app.schemas.enterprise import ApiKeyCreate, ApiKeyOut, ApiKeyCreatedResponse, AuditEventOut, FeatureFlagCreate, FeatureFlagOut
from app.schemas.token import TokenData
from app.database import get_db

router = APIRouter(tags=["enterprise"])


@router.get("/enterprise/stats")
async def platform_stats(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return platform-wide aggregate statistics for the dashboard."""
    from app.models import Project, Workflow, User

    async def count(model, **filters):
        q = select(func.count()).select_from(model)
        for col, val in filters.items():
            q = q.where(getattr(model, col) == val)
        result = await db.execute(q)
        return result.scalar_one_or_none() or 0

    total_projects    = await count(Project)
    total_workflows   = await count(Workflow)
    wf_completed      = await count(Workflow, status="COMPLETED")
    wf_active         = await count(Workflow, status="RUNNING")
    total_users       = await count(User)
    # ApprovalRequest uses "WAITING_FOR_APPROVAL"; legacy Approval table uses "PENDING"
    from app.models import ApprovalRequest
    pending_approvals = await count(ApprovalRequest, status="WAITING_FOR_APPROVAL")

    return {
        "success": True,
        "data": {
            "total_projects":    total_projects,
            "total_workflows":   total_workflows,
            "workflows_completed": wf_completed,
            "workflows_active":  wf_active,
            "total_users":       total_users,
            "pending_approvals": pending_approvals,
        },
        "error": None,
    }



# --- API Keys Routes ---
@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_in: ApiKeyCreate,
    current_user: TokenData = Depends(PermissionRequired("projects:write")),
    key_service: ApiKeyService = Depends(get_api_key_service),
    audit_service: AuditService = Depends(get_audit_service),
    request: Request = None
):
    user_id = UUID(current_user.scopes[0])
    key, plain_key = await key_service.create_key(user_id, key_in)
    
    # Audit log
    await audit_service.log_event(
        action="CREATE_API_KEY",
        resource=f"api_key:{key.api_key_id}",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None
    )

    return {
        "success": True,
        "data": {
            "api_key_id": str(key.api_key_id),
            "name": key.name,
            "prefix": key.prefix,
            "is_active": key.is_active,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "created_at": key.created_at.isoformat(),
            "plain_key": plain_key
        },
        "error": None
    }

@router.get("/api-keys", response_model=dict)
async def list_api_keys(
    current_user: TokenData = Depends(get_current_user),
    key_service: ApiKeyService = Depends(get_api_key_service)
):
    user_id = UUID(current_user.scopes[0])
    keys = await key_service.list_keys(user_id)
    return {
        "success": True,
        "data": [ApiKeyOut.model_validate(k) for k in keys],
        "error": None
    }

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    current_user: TokenData = Depends(PermissionRequired("projects:write")),
    key_service: ApiKeyService = Depends(get_api_key_service),
    audit_service: AuditService = Depends(get_audit_service),
    request: Request = None
):
    user_id = UUID(current_user.scopes[0])
    key = await key_service.revoke_key(key_id, user_id)
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
        
    await audit_service.log_event(
        action="REVOKE_API_KEY",
        resource=f"api_key:{key_id}",
        user_id=user_id,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None
    )
    return {"success": True, "data": {"message": "API Key revoked"}, "error": None}

# --- Audit Logs Routes ---
@router.get("/audit-events")
async def list_audit_events(
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    user_id = UUID(current_user.scopes[0])
    # Admin gets all, other roles get owned audit logs
    if current_user.role == "admin":
        events = await audit_service.repository.get_multi(skip=skip, limit=limit)
    else:
        events = await audit_service.repository.get_by_user(user_id, skip=skip, limit=limit)
    return {
        "success": True,
        "data": [AuditEventOut.model_validate(e) for e in events],
        "error": None
    }

# --- Feature Flags Routes ---
@router.post("/feature-flags", status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    flag_in: FeatureFlagCreate,
    current_user: TokenData = Depends(PermissionRequired("admin")),
    flag_service: FeatureFlagService = Depends(get_flag_service)
):
    try:
        flag = await flag_service.create_flag(flag_in)
        return {
            "success": True,
            "data": FeatureFlagOut.model_validate(flag),
            "error": None
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/feature-flags/{flag_name}/active")
async def check_feature_flag_active(
    flag_name: str,
    current_user: TokenData = Depends(get_current_user),
    flag_service: FeatureFlagService = Depends(get_flag_service)
):
    context = {"role": current_user.role, "user_id": current_user.scopes[0]}
    active = await flag_service.is_active(flag_name, context)
    return {
        "success": True,
        "data": {"name": flag_name, "is_active": active},
        "error": None
    }
