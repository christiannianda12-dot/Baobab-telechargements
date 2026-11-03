from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    kind: str
    base_url: str | None
    is_enabled: bool
    notes: str | None
