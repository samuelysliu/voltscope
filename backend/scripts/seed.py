import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Article, ArticleTag, ArticleTopic, ArticleTranslation, Author, Comment, Placement, Tag, Topic, User
from app.security.passwords import hash_password


async def main() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        admin = await session.scalar(select(User).where(User.email == settings.default_admin_email))
        if admin is None:
            admin = User(
                email=settings.default_admin_email,
                password_hash=hash_password(settings.default_admin_password),
                display_name="samuel",
                role="admin",
                email_verified=True,
            )
            session.add(admin)
            await session.flush()
        else:
            admin.password_hash = hash_password(settings.default_admin_password)
            admin.role = "admin"
            admin.is_active = True
            admin.email_verified = True

        author = await session.scalar(select(Author).where(Author.slug == "editorial-team"))
        if author is None:
            author = Author(
                slug="editorial-team",
                display_name="Editorial Team",
                bio_zh="Energy and charging technology editors",
                bio_en="Energy and charging technology editors",
            )
            session.add(author)
            await session.flush()

        default_topics = [
            ("ev", "電動車", "Electric Vehicles"),
            ("charging", "充電", "Charging"),
            ("charging-station", "充電樁", "Charging Stations"),
            ("charging-deals", "充電優惠", "Charging Deals"),
            ("smart-mobility", "智慧移動", "Smart Mobility"),
            ("energy", "能源", "Energy"),
            ("energy-storage", "儲能", "Energy Storage"),
        ]
        topics: list[Topic] = []
        for slug, zh, en in default_topics:
            topic = await session.scalar(select(Topic).where(Topic.slug == slug))
            if topic is None:
                topic = Topic(slug=slug, name_zh=zh, name_en=en)
                session.add(topic)
                await session.flush()
            else:
                topic.name_zh = zh
                topic.name_en = en
            topics.append(topic)

        tags: list[Tag] = []
        for index, (slug, zh, en) in enumerate(
            default_topics
        ):
            tag = await session.scalar(select(Tag).where(Tag.slug == slug))
            if tag is None:
                tag = Tag(slug=slug, name_zh=zh, name_en=en, sort_order=index)
                session.add(tag)
                await session.flush()
            else:
                tag.name_zh = zh
                tag.name_en = en
                tag.sort_order = index
            tags.append(tag)

        existing = await session.scalar(select(ArticleTranslation).where(ArticleTranslation.slug == "ev-charging-basics"))
        if existing is None:
            now = datetime.now(UTC)
            article = Article(
                author_id=author.id,
                status="published",
                is_featured=True,
                hero_image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1400&q=80",
                thumbnail_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=900&q=80",
                og_image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1200&q=80",
                published_at=now - timedelta(days=1),
                first_published_at=now - timedelta(days=1),
                created_by=admin.id,
                updated_by=admin.id,
                admin_author_id=admin.id,
            )
            session.add(article)
            await session.flush()
            session.add_all(
                [
                    ArticleTranslation(
                        article_id=article.id,
                        locale="en",
                        title="EV charging basics",
                        slug="ev-charging-basics",
                        excerpt="A practical guide to charging speeds, connectors, and home setup.",
                        content_json={"type": "doc"},
                        content_html="<p>EV charging planning starts with daily range, circuit capacity, and connector compatibility.</p>",
                        content_text="EV charging planning starts with daily range, circuit capacity, and connector compatibility.",
                        seo_title="EV Charging Basics",
                        seo_description="Learn the basics of EV charging speeds, connectors, and home setup.",
                        translation_status="published",
                    ),
                    ArticleTranslation(
                        article_id=article.id,
                        locale="zh-TW",
                        title="電動車充電入門",
                        slug="ev-charging-basics",
                        excerpt="快速理解充電速度、接頭、居家安裝與日常補能規劃。",
                        content_json={"type": "doc"},
                        content_html="<p>規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。公共快充適合長途補能，居家慢充則適合日常使用。</p><h2>重點摘要</h2><p>好的充電策略需要同時考慮安全、電費、車款相容性與未來擴充。</p>",
                        content_text="規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。",
                        seo_title="電動車充電入門",
                        seo_description="快速理解電動車充電速度、接頭與居家安裝。",
                        translation_status="published",
                    ),
                ]
            )
            session.add(ArticleTag(article_id=article.id, tag_id=tags[0].id))
            session.add(ArticleTopic(article_id=article.id, topic_id=topics[0].id, is_primary=True))
            session.add(
                Comment(
                    article_id=article.id,
                    author_name="Reader",
                    author_email="reader@example.com",
                    body="Helpful overview.",
                    status="approved",
                )
            )
        else:
            article = await session.get(Article, existing.article_id)
            if article is not None:
                article.is_featured = True
                article.hero_image_url = article.hero_image_url or "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1400&q=80"
                article.thumbnail_url = article.thumbnail_url or "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=900&q=80"
                article.og_image_url = article.og_image_url or "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1200&q=80"
                if await session.get(ArticleTopic, {"article_id": article.id, "topic_id": topics[0].id}) is None:
                    session.add(ArticleTopic(article_id=article.id, topic_id=topics[0].id, is_primary=True))
                zh_translation = await session.scalar(
                    select(ArticleTranslation).where(ArticleTranslation.article_id == article.id, ArticleTranslation.locale == "zh-TW")
                )
                if zh_translation is not None:
                    zh_translation.title = "電動車充電入門"
                    zh_translation.excerpt = "快速理解充電速度、接頭、居家安裝與日常補能規劃。"
                    zh_translation.content_html = "<p>規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。公共快充適合長途補能，居家慢充則適合日常使用。</p><h2>重點摘要</h2><p>好的充電策略需要同時考慮安全、電費、車款相容性與未來擴充。</p>"
                    zh_translation.content_text = "規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。"
                    zh_translation.seo_title = "電動車充電入門"
                    zh_translation.seo_description = "快速理解電動車充電速度、接頭與居家安裝。"

        for key, name in [("home_hero", "Home Hero"), ("home_featured", "Home Featured"), ("home_trending", "Home Trending")]:
            if await session.scalar(select(Placement).where(Placement.placement_key == key)) is None:
                session.add(Placement(placement_key=key, display_name=name, placement_type="article"))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
