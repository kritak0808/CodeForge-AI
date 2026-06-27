from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_project_service, get_current_user
from app.authz import PermissionRequired
from app.services.project import ProjectService
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut
from app.schemas.token import TokenData

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: TokenData = Depends(PermissionRequired("projects:create")),
    project_service: ProjectService = Depends(get_project_service)
):
    user_id = UUID(current_user.scopes[0])
    project = await project_service.create_project(user_id, project_in)
    return {
        "success": True,
        "data": ProjectOut.model_validate(project),
        "error": None
    }

@router.get("/")
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(PermissionRequired("projects:read")),
    project_service: ProjectService = Depends(get_project_service)
):
    user_id = UUID(current_user.scopes[0])
    if current_user.role == "admin":
        projects = await project_service.repository.get_multi(skip=skip, limit=limit)
    else:
        projects = await project_service.get_user_projects(user_id, skip=skip, limit=limit)
    
    return {
        "success": True,
        "data": [ProjectOut.model_validate(p) for p in projects],
        "error": None
    }

@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    current_user: TokenData = Depends(PermissionRequired("projects:read")),
    project_service: ProjectService = Depends(get_project_service)
):
    user_id = UUID(current_user.scopes[0])
    try:
        project = await project_service.get_project(project_id, user_id, current_user.role)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return {
            "success": True,
            "data": ProjectOut.model_validate(project),
            "error": None
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.put("/{project_id}")
async def update_project(
    project_id: UUID,
    project_in: ProjectUpdate,
    current_user: TokenData = Depends(PermissionRequired("projects:write")),
    project_service: ProjectService = Depends(get_project_service)
):
    user_id = UUID(current_user.scopes[0])
    try:
        project = await project_service.update_project(project_id, user_id, current_user.role, project_in)
        return {
            "success": True,
            "data": ProjectOut.model_validate(project),
            "error": None
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user: TokenData = Depends(PermissionRequired("projects:delete")),
    project_service: ProjectService = Depends(get_project_service)
):
    user_id = UUID(current_user.scopes[0])
    try:
        project = await project_service.delete_project(project_id, user_id, current_user.role)
        return {
            "success": True,
            "data": ProjectOut.model_validate(project),
            "error": None
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
