"""
Pydantic v2 schemas for the Database Agent (Milestone 7).

All schemas are read-oriented since the DatabaseAgent writes designs
autonomously. The REST layer exposes read + trigger endpoints only.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────────
# DatabaseEntity
# ──────────────────────────────────────────────────────────────────────────

class DatabaseEntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    design_id: uuid.UUID
    entity_name: str
    table_name: str
    description: Optional[str] = None
    columns: List[Any] = Field(default_factory=list)
    constraints: List[Any] = Field(default_factory=list)
    ddl: Optional[str] = None
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────
# DatabaseRelationship
# ──────────────────────────────────────────────────────────────────────────

class DatabaseRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relationship_id: uuid.UUID
    design_id: uuid.UUID
    from_entity: str
    to_entity: str
    relationship_type: str
    cardinality: str
    join_key: str
    notes: Optional[str] = None
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────
# DatabaseIndex
# ──────────────────────────────────────────────────────────────────────────

class DatabaseIndexRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index_id: uuid.UUID
    design_id: uuid.UUID
    table_name: str
    index_name: str
    columns: List[str] = Field(default_factory=list)
    index_type: str
    is_unique: bool
    partial_where: Optional[str] = None
    ddl: Optional[str] = None
    rationale: str
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────
# MigrationPlan
# ──────────────────────────────────────────────────────────────────────────

class MigrationPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: uuid.UUID
    design_id: uuid.UUID
    migration_version: str
    migration_script: str
    rollback_script: str
    status: str
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────────────────
# QueryOptimizationReport
# ──────────────────────────────────────────────────────────────────────────

class QueryOptimizationReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    optimization_id: uuid.UUID
    design_id: uuid.UUID
    problem_statement: str
    recommendation: str
    priority: str
    estimated_speedup: Optional[str] = None
    category: str
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────
# DatabaseDesign  (root record)
# ──────────────────────────────────────────────────────────────────────────

class DatabaseDesignSummary(BaseModel):
    """Lightweight listing view (no nested children)."""
    model_config = ConfigDict(from_attributes=True)

    design_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    report_id: Optional[uuid.UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime


class DatabaseDesignRead(DatabaseDesignSummary):
    """Full design record including DDL and ER diagrams but no child lists."""
    sql_schema: Optional[str] = None
    er_diagram_text: Optional[str] = None
    er_diagram_mermaid: Optional[str] = None
    notes: Optional[str] = None


class DatabaseDesignFullResponse(DatabaseDesignRead):
    """Complete response including all child collections."""
    entities: List[DatabaseEntityRead] = Field(default_factory=list)
    relationships: List[DatabaseRelationshipRead] = Field(default_factory=list)
    indexes: List[DatabaseIndexRead] = Field(default_factory=list)
    migration_plans: List[MigrationPlanRead] = Field(default_factory=list)
    optimizations: List[QueryOptimizationReportRead] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# Internal payload schema used by the agent worker
# ──────────────────────────────────────────────────────────────────────────

class ColumnDefinition(BaseModel):
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    comment: Optional[str] = None
    primary_key: bool = False
    unique: bool = False


class ConstraintDefinition(BaseModel):
    constraint_type: str          # PRIMARY_KEY | UNIQUE | FOREIGN_KEY | CHECK
    columns: List[str]
    references: Optional[str] = None   # "table(column)" for FK
    check_expression: Optional[str] = None


class EntityPayload(BaseModel):
    entity_name: str
    table_name: str
    description: Optional[str] = None
    columns: List[ColumnDefinition] = Field(default_factory=list)
    constraints: List[ConstraintDefinition] = Field(default_factory=list)
    ddl: Optional[str] = None


class RelationshipPayload(BaseModel):
    from_entity: str
    to_entity: str
    relationship_type: str
    cardinality: str
    join_key: str
    notes: Optional[str] = None


class IndexPayload(BaseModel):
    table_name: str
    index_name: str
    columns: List[str]
    index_type: str = "BTREE"
    is_unique: bool = False
    partial_where: Optional[str] = None
    ddl: Optional[str] = None
    rationale: str


class MigrationPayload(BaseModel):
    migration_version: str
    migration_script: str
    rollback_script: str


class OptimizationPayload(BaseModel):
    problem_statement: str
    recommendation: str
    priority: str = "MEDIUM"
    estimated_speedup: Optional[str] = None
    category: str = "OTHER"


class DatabaseDesignPayload(BaseModel):
    """Full output payload emitted by DatabaseAgent.execute()."""
    workflow_id: Optional[uuid.UUID] = None
    project_id: uuid.UUID
    report_id: Optional[uuid.UUID] = None
    sql_schema: Optional[str] = None
    er_diagram_text: Optional[str] = None
    er_diagram_mermaid: Optional[str] = None
    notes: Optional[str] = None
    entities: List[EntityPayload] = Field(default_factory=list)
    relationships: List[RelationshipPayload] = Field(default_factory=list)
    indexes: List[IndexPayload] = Field(default_factory=list)
    migration: Optional[MigrationPayload] = None
    optimizations: List[OptimizationPayload] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# API request bodies
# ──────────────────────────────────────────────────────────────────────────

class RegenerateRequest(BaseModel):
    """Body for POST /database/designs/{design_id}/regenerate"""
    reason: Optional[str] = Field(
        None, description="Human-readable reason for regeneration"
    )
