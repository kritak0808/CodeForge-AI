from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=1000)
    tech_stack: Dict[str, Any]
    repository_url: Optional[str] = Field(None, max_length=500)
    budget_usd_limit: Decimal = Field(default=Decimal("50.00"), ge=0)

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tech_stack: Optional[Dict[str, Any]] = None
    repository_url: Optional[str] = None
    budget_usd_limit: Optional[Decimal] = None

class ProjectOut(ProjectBase):
    project_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
