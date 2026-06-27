from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class TechnologyRecommendationBase(BaseModel):
    component_type: str
    technology_name: str
    version_spec: str
    suitability_reason: str

class TechnologyRecommendationOut(TechnologyRecommendationBase):
    recommendation_id: UUID
    report_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ArchitectureDecisionBase(BaseModel):
    title: str
    description: str
    status: str = "PROPOSED"
    rationale: str

class ArchitectureDecisionOut(ArchitectureDecisionBase):
    decision_id: UUID
    report_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ArchitectureReviewBase(BaseModel):
    decision: str
    comments: Optional[str] = None

class ArchitectureReviewOut(ArchitectureReviewBase):
    review_id: UUID
    report_id: UUID
    reviewer_id: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ArchitectureReportCreate(BaseModel):
    project_id: UUID
    requirements: str

class ArchitectureReportOut(BaseModel):
    report_id: UUID
    workflow_id: Optional[UUID] = None
    project_id: UUID
    requirements: str
    report_text: str
    complexity_score: int
    estimated_cost: float
    risk_assessment: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    decisions: List[ArchitectureDecisionOut] = []
    recommendations: List[TechnologyRecommendationOut] = []
    reviews: List[ArchitectureReviewOut] = []
    
    model_config = ConfigDict(from_attributes=True)
