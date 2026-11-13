from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedUser(BaseModel):
    """Identity fields read exclusively from a verified Firebase ID token."""

    model_config = ConfigDict(strict=True, frozen=True)

    uid: str = Field(min_length=1, max_length=128)
    email: str | None = None
    email_verified: bool = False
    display_name: str | None = Field(default=None, validation_alias="name")


class UserProfile(BaseModel):
    created_at: datetime | None = None


class CurrentUserResponse(BaseModel):
    uid: str
    email: str | None
    email_verified: bool
    display_name: str | None
    profile: UserProfile
