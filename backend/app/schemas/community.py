from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommunityPostCreate(BaseModel):
    content: str = Field(..., min_length=1)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    post_type: str = "general"


class UserBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class CommunityPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    post_type: str
    upvotes: int
    is_verified: bool
    user: UserBriefResponse
    comment_count: int = 0
    created_at: datetime


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[UUID] = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    upvotes: int
    user: UserBriefResponse
    created_at: datetime
    replies: Optional[List["CommentResponse"]] = None
