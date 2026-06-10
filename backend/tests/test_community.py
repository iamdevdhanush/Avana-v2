import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.community_post import CommunityPost, PostStatus
from app.models.comment import Comment


@pytest.mark.asyncio
@pytest.mark.community
async def test_create_post(async_client: AsyncClient, auth_headers):
    payload = {
        "content": "This is a test community post about safety in the area.",
        "post_type": "general",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location_name": "MG Road, Bengaluru",
    }
    response = await async_client.post("/api/v1/community/posts", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == payload["content"]
    assert data["post_type"] == "general"
    assert data["latitude"] == 12.9716
    assert data["upvotes"] == 0
    assert data["is_verified"] is False
    assert data["comment_count"] == 0
    assert "user" in data
    assert data["user"]["name"] == "Test User"


@pytest.mark.asyncio
@pytest.mark.community
async def test_create_post_empty_content(async_client: AsyncClient, auth_headers):
    payload = {"content": "", "post_type": "general"}
    response = await async_client.post("/api/v1/community/posts", json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.community
async def test_list_posts(async_client: AsyncClient, db_session, test_user):
    for i in range(3):
        post = CommunityPost(
            id=uuid.uuid4(),
            user_id=test_user.id,
            content=f"List post {i}",
            post_type="general",
            status=PostStatus.ACTIVE,
            upvotes=0,
            downvotes=0,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(post)
    await db_session.flush()

    response = await async_client.get("/api/v1/community/posts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    for post in data:
        assert "content" in post
        assert "user" in post
        assert "comment_count" in post


@pytest.mark.asyncio
@pytest.mark.community
async def test_list_posts_pagination(async_client: AsyncClient, db_session, test_user):
    for i in range(5):
        post = CommunityPost(
            id=uuid.uuid4(),
            user_id=test_user.id,
            content=f"Page post {i}",
            post_type="general",
            status=PostStatus.ACTIVE,
            upvotes=0,
            downvotes=0,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(post)
    await db_session.flush()

    response = await async_client.get("/api/v1/community/posts?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


@pytest.mark.asyncio
@pytest.mark.community
async def test_get_post_detail(async_client: AsyncClient, sample_post):
    response = await async_client.get(f"/api/v1/community/posts/{sample_post.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_post.id)
    assert data["content"] == sample_post.content
    assert data["post_type"] == sample_post.post_type
    assert "user" in data


@pytest.mark.asyncio
@pytest.mark.community
async def test_get_post_not_found(async_client: AsyncClient):
    fake_id = uuid.uuid4()
    response = await async_client.get(f"/api/v1/community/posts/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.community
async def test_create_comment(async_client: AsyncClient, auth_headers, sample_post):
    payload = {"content": "This is a test comment on the post."}
    response = await async_client.post(
        f"/api/v1/community/posts/{sample_post.id}/comments", json=payload, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "This is a test comment on the post."
    assert data["upvotes"] == 0
    assert "user" in data
    assert data["user"]["name"] == "Test User"


@pytest.mark.asyncio
@pytest.mark.community
async def test_create_comment_post_not_found(async_client: AsyncClient, auth_headers):
    fake_id = uuid.uuid4()
    payload = {"content": "Comment on non-existent post"}
    response = await async_client.post(
        f"/api/v1/community/posts/{fake_id}/comments", json=payload, headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.community
async def test_list_comments(async_client: AsyncClient, sample_post, test_user, db_session):
    for i in range(3):
        comment = Comment(
            id=uuid.uuid4(),
            post_id=sample_post.id,
            user_id=test_user.id,
            content=f"Comment {i}",
            upvotes=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(comment)
    await db_session.flush()

    response = await async_client.get(f"/api/v1/community/posts/{sample_post.id}/comments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    for comment in data:
        assert "content" in comment
        assert "user" in comment


@pytest.mark.asyncio
@pytest.mark.community
async def test_vote_post(async_client: AsyncClient, auth_headers, sample_post):
    response = await async_client.post(
        f"/api/v1/community/posts/{sample_post.id}/vote?vote_type=up", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upvotes"] == 1


@pytest.mark.asyncio
@pytest.mark.community
async def test_vote_post_down(async_client: AsyncClient, auth_headers, sample_post):
    response = await async_client.post(
        f"/api/v1/community/posts/{sample_post.id}/vote?vote_type=down", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["downvotes"] == 1


@pytest.mark.asyncio
@pytest.mark.community
async def test_vote_post_invalid(async_client: AsyncClient, auth_headers, sample_post):
    response = await async_client.post(
        f"/api/v1/community/posts/{sample_post.id}/vote?vote_type=invalid", headers=auth_headers
    )
    assert response.status_code == 400
    data = response.json()
    assert "invalid" in data["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.community
async def test_vote_post_not_found(async_client: AsyncClient, auth_headers):
    fake_id = uuid.uuid4()
    response = await async_client.post(
        f"/api/v1/community/posts/{fake_id}/vote?vote_type=up", headers=auth_headers
    )
    assert response.status_code == 404
