import hashlib

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select

from app.api.v1.deps import SessionDep, current_verified_member
from app.core.errors import AppError
from app.models import Article, ArticleLike, Comment, User
from app.schemas.content import CommentOut, MemberCommentCreate, MemberLikeOut

router = APIRouter(prefix="/member", tags=["member"])


def member_like_hash(article_id: str, user_id: str) -> str:
    return hashlib.sha256(f"member-like:{article_id}:{user_id}".encode("utf-8")).hexdigest()


@router.post("/articles/{article_id}/like", response_model=MemberLikeOut)
async def toggle_like(article_id: str, session: SessionDep, user: User = Depends(current_verified_member)) -> MemberLikeOut:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)

    existing = await session.scalar(select(ArticleLike).where(ArticleLike.article_id == article_id, ArticleLike.user_id == user.id))
    if existing is not None:
        await session.execute(delete(ArticleLike).where(ArticleLike.id == existing.id))
        article.likes_count = max(0, article.likes_count - 1)
        liked = False
    else:
        session.add(
            ArticleLike(
                article_id=article_id,
                user_id=user.id,
                visitor_key_hash=member_like_hash(article_id, user.id),
            )
        )
        article.likes_count += 1
        liked = True
    await session.commit()
    count = await session.scalar(select(func.count()).select_from(ArticleLike).where(ArticleLike.article_id == article_id))
    return MemberLikeOut(liked=liked, count=count or 0)


@router.post("/articles/{article_id}/comments", response_model=CommentOut, status_code=201)
async def create_member_comment(
    article_id: str,
    payload: MemberCommentCreate,
    session: SessionDep,
    user: User = Depends(current_verified_member),
) -> CommentOut:
    article = await session.get(Article, article_id)
    if article is None or article.deleted_at is not None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    if not article.is_comments_enabled:
        raise AppError("COMMENTS_DISABLED", "Comments are disabled for this article", 400)
    comment = Comment(
        article_id=article_id,
        user_id=user.id,
        author_name=user.display_name,
        author_email=user.email,
        body=payload.content,
        content=payload.content,
        status="visible",
    )
    session.add(comment)
    article.comments_count += 1
    await session.commit()
    await session.refresh(comment)
    return CommentOut(
        id=comment.id,
        author_name=comment.author_name,
        body=comment.content or comment.body,
        status=comment.status,
        created_at=comment.created_at,
    )
