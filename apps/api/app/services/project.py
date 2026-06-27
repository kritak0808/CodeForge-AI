from typing import List, Optional
from uuid import UUID
from app.models import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    async def create_project(self, user_id: UUID, project_in: ProjectCreate) -> Project:
        db_project = Project(
            user_id=user_id,
            name=project_in.name,
            description=project_in.description,
            tech_stack=project_in.tech_stack,
            repository_url=project_in.repository_url,
            budget_usd_limit=project_in.budget_usd_limit
        )
        return await self.repository.create(db_project)

    async def get_project(self, project_id: UUID, user_id: UUID, user_role: str) -> Optional[Project]:
        db_project = await self.repository.get(project_id)
        if not db_project:
            return None
        # Enforce tenancy rules unless user is Admin or Auditor
        if db_project.user_id != user_id and user_role not in ["admin", "auditor"]:
            raise PermissionError("Access to this project is denied")
        return db_project

    async def get_user_projects(self, user_id: UUID, skip: int = 0, limit: int = 100) -> List[Project]:
        return await self.repository.get_by_owner(user_id, skip=skip, limit=limit)

    async def update_project(self, project_id: UUID, user_id: UUID, user_role: str, project_in: ProjectUpdate) -> Project:
        db_project = await self.get_project(project_id, user_id, user_role)
        if not db_project:
            raise ValueError("Project not found")
        if db_project.user_id != user_id and user_role != "admin":
            raise PermissionError("Access denied")
            
        update_data = project_in.model_dump(exclude_unset=True)
        return await self.repository.update(db_project, update_data)

    async def delete_project(self, project_id: UUID, user_id: UUID, user_role: str) -> Project:
        db_project = await self.get_project(project_id, user_id, user_role)
        if not db_project:
            raise ValueError("Project not found")
        if db_project.user_id != user_id and user_role != "admin":
            raise PermissionError("Access denied")
            
        return await self.repository.remove(project_id)
