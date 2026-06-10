import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Boolean, Integer, JSON, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class PostStatus(str, enum.Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    REPORTED = "reported"


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=True)
    post_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    downvotes: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[PostStatus] = mapped_column(SAEnum(PostStatus), default=PostStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="community_posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
