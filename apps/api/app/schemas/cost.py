"""
Pydantic schemas for the Cost Optimization Agent (Milestone 16).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Child payload schemas (inbound from agent worker) ─────────────────────────

class CostReportPayload(BaseModel):
    category: str
    current_cost: float = 0.0
    projected_cost: float = 0.0
    notes: Optional[str] = None


class ResourceUsageMetricPayload(BaseModel):
    resource_type: str
    utilization_percent: float = 0.0
    consumption: float = 0.0
    unit: str = "%"


class OptimizationRecommendationPayload(BaseModel):
    title: str
    description: str
    impact_level: str = "MEDIUM"
    estimated_savings: float = 0.0
    category: Optional[str] = None


class SavingsEstimatePayload(BaseModel):
    monthly_savings: float = 0.0
    annual_savings: float = 0.0
    confidence_level: str = "MEDIUM"
    assumptions: Optional[str] = None


class CostAlertPayload(BaseModel):
    severity: str = "WARNING"
    message: str
    current_cost: float = 0.0
    budget_limit: float = 0.0
    status: str = "OPEN"


# ── Root generation payload ───────────────────────────────────────────────────

class CostGenerationPayload(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    total_cost: float = 0.0
    estimated_monthly_cost: float = 0.0
    currency: str = "USD"
    cost_reports: List[CostReportPayload] = Field(default_factory=list)
    resource_usage_metrics: List[ResourceUsageMetricPayload] = Field(default_factory=list)
    optimization_recommendations: List[OptimizationRecommendationPayload] = Field(default_factory=list)
    savings_estimates: List[SavingsEstimatePayload] = Field(default_factory=list)
    cost_alerts: List[CostAlertPayload] = Field(default_factory=list)


# ── REST request bodies ───────────────────────────────────────────────────────

class GenerateCostRequest(BaseModel):
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None


class RegenerateCostRequest(BaseModel):
    reason: Optional[str] = None


class BudgetPolicyRequest(BaseModel):
    project_id: uuid.UUID
    monthly_budget: float
    alert_threshold: float = 0.8
    currency: str = "USD"
    is_active: bool = True


# ── Read schemas (outbound) ───────────────────────────────────────────────────

class CostGenerationRead(BaseModel):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    total_cost: float
    estimated_monthly_cost: float
    currency: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CostReportRead(BaseModel):
    report_id: uuid.UUID
    generation_id: uuid.UUID
    category: str
    current_cost: float
    projected_cost: float
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResourceUsageMetricRead(BaseModel):
    metric_id: uuid.UUID
    generation_id: uuid.UUID
    resource_type: str
    utilization_percent: float
    consumption: float
    unit: str
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OptimizationRecommendationRead(BaseModel):
    recommendation_id: uuid.UUID
    generation_id: uuid.UUID
    title: str
    description: str
    impact_level: str
    estimated_savings: float
    category: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SavingsEstimateRead(BaseModel):
    estimate_id: uuid.UUID
    generation_id: uuid.UUID
    monthly_savings: float
    annual_savings: float
    confidence_level: str
    assumptions: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BudgetPolicyRead(BaseModel):
    policy_id: uuid.UUID
    project_id: uuid.UUID
    monthly_budget: float
    alert_threshold: float
    currency: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CostAlertRead(BaseModel):
    alert_id: uuid.UUID
    generation_id: uuid.UUID
    policy_id: Optional[uuid.UUID] = None
    severity: str
    message: str
    current_cost: float
    budget_limit: float
    status: str
    fired_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CostGenerationFullResponse(BaseModel):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    status: str
    total_cost: float
    estimated_monthly_cost: float
    currency: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    cost_reports: List[CostReportRead] = Field(default_factory=list)
    resource_usage_metrics: List[ResourceUsageMetricRead] = Field(default_factory=list)
    optimization_recommendations: List[OptimizationRecommendationRead] = Field(default_factory=list)
    savings_estimates: List[SavingsEstimateRead] = Field(default_factory=list)
    cost_alerts: List[CostAlertRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
