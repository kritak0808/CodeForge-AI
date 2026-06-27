"""
Pydantic v2 schemas for the QA Agent (Milestone 10).

Naming convention:
  *Read      – ORM → API response (from_attributes=True)
  *Payload   – internal agent output consumed by QaGenerationService
  *Request   – inbound API request body
  *Summary   – lightweight list-view response
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── QaTestSuite schemas ──────────────────────────────────────────────────────

class QaTestSuiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    suite_id: uuid.UUID
    generation_id: uuid.UUID
    suite_name: str
    suite_type: str
    file_path: Optional[str] = None
    code: str
    created_at: datetime


class QaTestSuitePayload(BaseModel):
    suite_name: str
    suite_type: str
    file_path: Optional[str] = None
    code: str


# ── QaTestCase schemas ───────────────────────────────────────────────────────

class QaTestCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID
    generation_id: uuid.UUID
    suite_id: Optional[uuid.UUID] = None
    case_name: str
    description: Optional[str] = None
    test_code: str
    created_at: datetime


class QaTestCasePayload(BaseModel):
    case_name: str
    description: Optional[str] = None
    test_code: str


# ── QaTestRun schemas ────────────────────────────────────────────────────────

class QaTestRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    generation_id: uuid.UUID
    runner_name: str
    status: str
    summary_json: Optional[dict] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    created_at: datetime


class QaTestRunPayload(BaseModel):
    runner_name: str
    status: str
    summary_json: Optional[dict] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


# ── QaBugReport schemas ───────────────────────────────────────────────────────

class QaBugReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bug_id: uuid.UUID
    generation_id: uuid.UUID
    title: str
    severity: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    metadata_json: Optional[dict] = None
    created_at: datetime


class QaBugReportPayload(BaseModel):
    title: str
    severity: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    metadata_json: Optional[dict] = None


# ── QaCoverageReport schemas ──────────────────────────────────────────────────

class QaCoverageReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    generation_id: uuid.UUID
    coverage_type: str
    line_coverage: float
    branch_coverage: Optional[float] = None
    summary_json: Optional[dict] = None
    created_at: datetime


class QaCoverageReportPayload(BaseModel):
    coverage_type: str
    line_coverage: float
    branch_coverage: Optional[float] = None
    summary_json: Optional[dict] = None


# ── QaQualityMetrics schemas ──────────────────────────────────────────────────

class QaQualityMetricsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metrics_id: uuid.UUID
    generation_id: uuid.UUID
    overall_score: float
    reliability_score: Optional[float] = None
    security_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    details_json: Optional[dict] = None
    created_at: datetime


class QaQualityMetricsPayload(BaseModel):
    overall_score: float
    reliability_score: Optional[float] = None
    security_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    details_json: Optional[dict] = None


# ── QaGeneration composite schemas ───────────────────────────────────────────

class QaGenerationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class QaGenerationRead(QaGenerationSummary):
    pass


class QaGenerationFullResponse(QaGenerationRead):
    """Complete generation with all child artifacts."""
    test_suites: List[QaTestSuiteRead] = Field(default_factory=list)
    test_cases: List[QaTestCaseRead] = Field(default_factory=list)
    test_runs: List[QaTestRunRead] = Field(default_factory=list)
    bug_reports: List[QaBugReportRead] = Field(default_factory=list)
    coverage_reports: List[QaCoverageReportRead] = Field(default_factory=list)
    quality_metrics: List[QaQualityMetricsRead] = Field(default_factory=list)


# ── Internal agent payload ────────────────────────────────────────────────────

class QaGenerationPayload(BaseModel):
    """Payload produced by QAAgent and consumed by QaGenerationService."""
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    test_suites: List[QaTestSuitePayload] = Field(default_factory=list)
    test_cases: List[QaTestCasePayload] = Field(default_factory=list)
    test_runs: List[QaTestRunPayload] = Field(default_factory=list)
    bug_reports: List[QaBugReportPayload] = Field(default_factory=list)
    coverage_reports: List[QaCoverageReportPayload] = Field(default_factory=list)
    quality_metrics: List[QaQualityMetricsPayload] = Field(default_factory=list)


# ── API request bodies ────────────────────────────────────────────────────────

class GenerateQaRequest(BaseModel):
    """Body for POST /qa/generate."""
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    backend_generation_id: Optional[uuid.UUID] = None
    frontend_generation_id: Optional[uuid.UUID] = None
    design_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None


class RegenerateQaRequest(BaseModel):
    """Body for POST /qa/generations/{id}/regenerate."""
    reason: Optional[str] = None
