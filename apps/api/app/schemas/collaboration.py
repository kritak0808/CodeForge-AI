"""
Pydantic v2 schemas for the Collaboration Engine (Milestone 14).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


# ── Request / Input schemas ──────────────────────────────────────────────────

class StartCollaborationRequest(BaseModel):
    project_id: uuid.UUID
    workflow_id: uuid.UUID


class SendMessageRequest(BaseModel):
    conversation_id: uuid.UUID
    sender_agent: str
    recipient_agent: Optional[str] = None
    content: str
    message_metadata: Optional[Dict[str, Any]] = None


class CreateReviewRequest(BaseModel):
    session_id: uuid.UUID
    reviewer_agent: str
    target_agent: str
    artifact_type: str
    artifact_id: uuid.UUID
    status: str  # APPROVED, REWORK_REQUESTED
    comments: Optional[str] = None


class CastVoteRequest(BaseModel):
    session_id: uuid.UUID
    topic: str
    voter_agent: str
    decision: str  # YES, NO, ABSTAIN


class CreateConflictRequest(BaseModel):
    session_id: uuid.UUID
    title: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL


class ResolveConflictRequest(BaseModel):
    conflict_id: uuid.UUID
    resolved_by: str
    resolution_strategy: str
    details: str


# ── Read schemas ─────────────────────────────────────────────────────────────

class AgentMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: uuid.UUID
    conversation_id: uuid.UUID
    sender_agent: str
    recipient_agent: Optional[str] = None
    content: str
    message_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class AgentConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    session_id: uuid.UUID
    title: str
    created_at: datetime
    messages: List[AgentMessageRead] = Field(default_factory=list)


class AgentReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    session_id: uuid.UUID
    reviewer_agent: str
    target_agent: str
    artifact_type: str
    artifact_id: uuid.UUID
    status: str
    comments: Optional[str] = None
    created_at: datetime


class AgentVoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vote_id: uuid.UUID
    session_id: uuid.UUID
    topic: str
    voter_agent: str
    decision: str
    voted_at: datetime


class AgentResolutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resolution_id: uuid.UUID
    conflict_id: uuid.UUID
    resolved_by: str
    resolution_strategy: str
    details: str
    resolved_at: datetime


class AgentConflictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_id: uuid.UUID
    session_id: uuid.UUID
    title: str
    description: str
    severity: str
    status: str
    created_at: datetime
    resolutions: List[AgentResolutionRead] = Field(default_factory=list)


class AgentCollaborationSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime


class AgentCollaborationSessionRead(AgentCollaborationSessionSummary):
    conversations: List[AgentConversationRead] = Field(default_factory=list)
    reviews: List[AgentReviewRead] = Field(default_factory=list)
    votes: List[AgentVoteRead] = Field(default_factory=list)
    conflicts: List[AgentConflictRead] = Field(default_factory=list)
