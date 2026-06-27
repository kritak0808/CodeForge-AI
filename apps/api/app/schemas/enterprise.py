from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# --- API Keys Schemas ---
class ApiKeyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_at: Optional[datetime] = None

class ApiKeyCreate(ApiKeyBase):
    pass

class ApiKeyOut(ApiKeyBase):
    api_key_id: UUID
    user_id: UUID
    prefix: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ApiKeyCreatedResponse(ApiKeyOut):
    plain_key: str # The unhashed API key returned only ONCE during creation

# --- User Session Schemas ---
class UserSessionOut(BaseModel):
    session_id: UUID
    user_id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_active: bool
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# --- Audit Event Schemas ---
class AuditEventBase(BaseModel):
    action: str
    resource: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class AuditEventCreate(AuditEventBase):
    user_id: Optional[UUID] = None

class AuditEventOut(AuditEventBase):
    event_id: UUID
    user_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Feature Flags Schemas ---
class FeatureFlagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_enabled: bool = False
    conditions: Optional[Dict[str, Any]] = None

class FeatureFlagCreate(FeatureFlagBase):
    pass

class FeatureFlagOut(FeatureFlagBase):
    flag_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
