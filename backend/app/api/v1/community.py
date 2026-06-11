import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models.community_post import CommunityPost, PostStatus
from app.models.comment import Comment
from app.models.user import User
from app.schemas.community import (
    CommunityPostCreate,
    CommunityPostResponse,
    UserBriefResponse,
    CommentCreate,
    CommentResponse,
)

router = APIRouter(prefix="/community", tags=["Community"])


@router.get("/posts", response_model=list[CommunityPostResponse])
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    post_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(CommunityPost)
        .options(selectinload(CommunityPost.user), selectinload(CommunityPost.comments))
        .where(CommunityPost.status == PostStatus.ACTIVE)
        .order_by(CommunityPost.created_at.desc())
    )
    if post_type:
        query = query.where(CommunityPost.post_type == post_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    posts = result.scalars().all()

    return [
        CommunityPostResponse(
            id=p.id,
            content=p.content,
            latitude=p.latitude,
            longitude=p.longitude,
            location_name=p.location_name,
            post_type=p.post_type,
            upvotes=p.upvotes,
            is_verified=p.is_verified,
            user=UserBriefResponse(
                id=p.user.id,
                name=p.user.name,
                avatar_url=p.user.avatar_url,
            ),
            comment_count=len(p.comments) if p.comments else 0,
            created_at=p.created_at,
        )
        for p in posts
    ]


@router.post("/posts", response_model=CommunityPostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: CommunityPostCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    post = CommunityPost(
        id=uuid.uuid4(),
        user_id=user.id,
        content=body.content,
        latitude=body.latitude,
        longitude=body.longitude,
        location_name=body.location_name,
        post_type=body.post_type,
        status=PostStatus.ACTIVE,
        upvotes=0,
        downvotes=0,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(post)
    await db.flush()

    return CommunityPostResponse(
        id=post.id,
        content=post.content,
        latitude=post.latitude,
        longitude=post.longitude,
        location_name=post.location_name,
        post_type=post.post_type,
        upvotes=post.upvotes,
        is_verified=post.is_verified,
        user=UserBriefResponse(id=user.id, name=user.name, avatar_url=user.avatar_url),
        comment_count=0,
        created_at=post.created_at,
    )


@router.get("/posts/{id}", response_model=CommunityPostResponse)
async def get_post(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CommunityPost)
        .options(selectinload(CommunityPost.user), selectinload(CommunityPost.comments))
        .where(CommunityPost.id == id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return CommunityPostResponse(
        id=post.id,
        content=post.content,
        latitude=post.latitude,
        longitude=post.longitude,
        location_name=post.location_name,
        post_type=post.post_type,
        upvotes=post.upvotes,
        is_verified=post.is_verified,
        user=UserBriefResponse(
            id=post.user.id,
            name=post.user.name,
            avatar_url=post.user.avatar_url,
        ),
        comment_count=len(post.comments) if post.comments else 0,
        created_at=post.created_at,
    )


@router.post("/posts/{id}/vote")
async def vote_post(
    id: uuid.UUID,
    vote_type: str = Query(..., description="'up' or 'down'"),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CommunityPost).where(CommunityPost.id == id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if vote_type not in ("up", "down"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vote type")

    voter_id = str(user.id)
    voters = post.voters or {}
    existing_vote = voters.get(voter_id)

    if existing_vote == vote_type:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already voted")

    if existing_vote == "up":
        post.upvotes = max(0, post.upvotes - 1)
    elif existing_vote == "down":
        post.downvotes = max(0, post.downvotes - 1)

    if vote_type == "up":
        post.upvotes += 1
    else:
        post.downvotes += 1

    voters[voter_id] = vote_type
    post.voters = voters
    post.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": str(post.id), "upvotes": post.upvotes, "downvotes": post.downvotes}


@router.get("/posts/{id}/comments", response_model=list[CommentResponse])
async def get_comments(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post_result = await db.execute(select(CommunityPost).where(CommunityPost.id == id))
    if not post_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.user), selectinload(Comment.replies).selectinload(Comment.user))
        .where(Comment.post_id == id, Comment.parent_id.is_(None))
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()

    def _build_reply(reply: Comment) -> CommentResponse:
        return CommentResponse(
            id=reply.id,
            content=reply.content,
            upvotes=reply.upvotes,
            user=UserBriefResponse(id=reply.user.id, name=reply.user.name, avatar_url=reply.user.avatar_url),
            created_at=reply.created_at,
            replies=[
                _build_reply(r) for r in (reply.replies or [])
            ] if reply.replies else None,
        )

    return [
        CommentResponse(
            id=c.id,
            content=c.content,
            upvotes=c.upvotes,
            user=UserBriefResponse(id=c.user.id, name=c.user.name, avatar_url=c.user.avatar_url),
            created_at=c.created_at,
            replies=[_build_reply(r) for r in (c.replies or [])] if c.replies else None,
        )
        for c in comments
    ]


@router.post("/posts/{id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    id: uuid.UUID,
    body: CommentCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    post_result = await db.execute(select(CommunityPost).where(CommunityPost.id == id))
    if not post_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if body.parent_id:
        parent_result = await db.execute(
            select(Comment).where(Comment.id == body.parent_id, Comment.post_id == id)
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

    comment = Comment(
        id=uuid.uuid4(),
        post_id=id,
        user_id=user.id,
        parent_id=body.parent_id,
        content=body.content,
        upvotes=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    await db.flush()

    return CommentResponse(
        id=comment.id,
        content=comment.content,
        upvotes=comment.upvotes,
        user=UserBriefResponse(id=user.id, name=user.name, avatar_url=user.avatar_url),
        created_at=comment.created_at,
        replies=None,
    )
