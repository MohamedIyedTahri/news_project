import logging
from typing import Any, Dict, List, Optional
import json
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_session_factory
from .models import Article, FullContentStatus, ProcessedArticle

DB_PATH = "news_articles.db"  # Deprecated; preserved for backwards compatibility.

logger = logging.getLogger(__name__)


class NewsStorage:
    """High-level data access layer backed by SQLAlchemy sessions."""

    def __init__(self, database_url: Optional[str] = None, db_path: Optional[str] = None):
        if database_url:
            self._session_factory = get_session_factory(database_url)
        elif db_path:
            # Explicit SQLite override (legacy support for spark utilities/tests)
            sqlite_url = f"sqlite:///{db_path}"
            self._session_factory = get_session_factory(sqlite_url)
        else:
            self._session_factory = get_session_factory()

    @contextmanager
    def _session(self) -> Session:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_article(self, article):
        """Insert or update an article.

        Expected keys in article dict:
            title, link, publish_date, source, category, content (summary), optional full_content

        Behavior:
            - Uses INSERT OR IGNORE to avoid duplicate links.
            - If row exists and full_content provided while DB value is NULL/empty, performs an UPDATE.
        """
        required = ["title", "link", "publish_date", "source", "category", "content"]
        for k in required:
            if k not in article:
                logger.warning(f"save_article missing required field '{k}' for link={article.get('link')} - skipping")
                return False
        desired_status = article.get("full_content_status")
        status_enum = None
        if desired_status:
            try:
                status_enum = FullContentStatus(desired_status)
            except ValueError:
                logger.warning("Unknown full_content_status '%s' for link=%s", desired_status, article.get("link"))

        inserted = False
        try:
            with self._session() as session:
                existing: Article | None = session.execute(
                    select(Article).where(Article.link == article["link"])
                ).scalar_one_or_none()

                if existing is None:
                    record = Article(
                        title=article["title"],
                        link=article["link"],
                        publish_date=article.get("publish_date"),
                        source=article.get("source"),
                        category=article.get("category"),
                        content=article.get("content"),
                        full_content=article.get("full_content"),
                        full_content_status=status_enum or (
                            FullContentStatus.SUCCESS if article.get("full_content") else None
                        ),
                    )
                    session.add(record)
                    try:
                        session.flush()
                        inserted = True
                    except IntegrityError:
                        session.rollback()
                        inserted = False
                        existing = session.execute(
                            select(Article).where(Article.link == article["link"])
                        ).scalar_one_or_none()
                        if existing is None:
                            raise

                if existing:
                    updated = False
                    if not existing.content and article.get("content"):
                        existing.content = article.get("content")
                        updated = True
                    if article.get("title") and article["title"] != existing.title:
                        existing.title = article["title"]
                        updated = True
                    if article.get("publish_date") and article["publish_date"] != existing.publish_date:
                        existing.publish_date = article["publish_date"]
                        updated = True
                    if article.get("source") and article["source"] != existing.source:
                        existing.source = article["source"]
                        updated = True
                    if article.get("category") and article["category"] != existing.category:
                        existing.category = article["category"]
                        updated = True

                    new_full_content = article.get("full_content")
                    if new_full_content and not existing.full_content:
                        existing.full_content = new_full_content
                        if status_enum:
                            existing.full_content_status = status_enum
                        else:
                            existing.full_content_status = FullContentStatus.SUCCESS
                        updated = True
                    elif status_enum and existing.full_content_status != status_enum:
                        existing.full_content_status = status_enum
                        updated = True

                    if updated:
                        session.add(existing)
            return inserted
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error(f"Error saving article link={article.get('link')}: {e}")
            return False

    # ------------------------ Processed Article Helpers ------------------------
    def save_processed_article(
        self,
        *,
        article_id: int,
        tokens: List[str],
        feature_vector: List[float],
        token_count: int,
        pipeline_version: str,
        processed_at: Optional[str] = None,
    ) -> bool:
        """Upsert processed NLP features for a given article."""
        processed_value = processed_at or datetime.utcnow().isoformat(timespec="seconds")
        if isinstance(processed_value, str):
            try:
                processed_dt = datetime.fromisoformat(processed_value.replace("Z", ""))
            except ValueError:
                processed_dt = datetime.utcnow()
        else:  # pragma: no cover - future-proof for datetime inputs
            processed_dt = processed_value
        try:
            tokens_json = json.dumps(tokens)
            vector_json = json.dumps(feature_vector)
            with self._session() as session:
                existing: ProcessedArticle | None = session.get(ProcessedArticle, article_id)
                if existing is None:
                    existing = ProcessedArticle(
                        article_id=article_id,
                        token_count=token_count,
                        tokens=tokens_json,
                        feature_vector=vector_json,
                        pipeline_version=pipeline_version,
                        processed_at=processed_dt,
                    )
                    session.add(existing)
                else:
                    existing.token_count = token_count
                    existing.tokens = tokens_json
                    existing.feature_vector = vector_json
                    existing.pipeline_version = pipeline_version
                    existing.processed_at = processed_dt
                    session.add(existing)
            return True
        except Exception as exc:  # pragma: no cover
            logger.error(f"Error saving processed article id={article_id}: {exc}")
            return False

    def fetch_articles_for_processing(
        self,
        *,
        since_id: Optional[int] = None,
        limit: Optional[int] = None,
        min_length: int = 50,
        prefer_full_content: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return articles prepared for downstream Spark processing."""
        preferred = (
            func.coalesce(func.nullif(Article.full_content, ""), func.nullif(Article.content, ""))
            if prefer_full_content
            else func.coalesce(func.nullif(Article.content, ""), func.nullif(Article.full_content, ""))
        )

        trimmed = func.trim(preferred)
        query = select(Article.id, preferred.label("clean_text")).where(
            preferred.is_not(None),
            func.length(trimmed) >= min_length,
        )

        if since_id is not None:
            query = query.where(Article.id > since_id)

        query = query.order_by(Article.id.asc())
        if limit is not None:
            query = query.limit(limit)

        try:
            with self._session() as session:
                rows = session.execute(query).all()
                return [
                    {"article_id": row.id, "clean_text": row.clean_text}
                    for row in rows
                    if row.clean_text
                ]
        except Exception as exc:  # pragma: no cover
            logger.error(f"Error fetching articles for processing: {exc}")
            return []

    def get_latest_processed_article_id(self) -> int:
        """Return the highest article id already processed by Spark."""
        try:
            with self._session() as session:
                result = session.execute(select(func.coalesce(func.max(ProcessedArticle.article_id), 0)))
                value = result.scalar_one()
                return int(value or 0)
        except Exception as exc:  # pragma: no cover
            logger.error(f"Error retrieving latest processed article id: {exc}")
            return 0

    def get_statistics(self):
        """
        Get database statistics.
        
        Returns:
            dict: Statistics about stored articles
        """
        try:
            with self._session() as session:
                total_articles = session.execute(select(func.count(Article.id))).scalar_one()

                category_rows = session.execute(
                    select(Article.category, func.count(Article.id)).group_by(Article.category)
                ).all()
                by_category = {row.category or "(uncategorized)": row.count_1 for row in category_rows}

                source_rows = session.execute(
                    select(Article.source, func.count(Article.id))
                    .group_by(Article.source)
                    .order_by(func.count(Article.id).desc())
                    .limit(10)
                ).all()
                by_source = {row.source or "(unknown)": row.count_1 for row in source_rows}

                return {
                    "total_articles": int(total_articles),
                    "by_category": by_category,
                    "top_sources": by_source,
                }
        except Exception as e:  # pragma: no cover
            print(f"Error getting statistics: {e}")
            return {}

    def close(self):
        """Provided for backwards compatibility; sessions are scoped per call."""
        return None

    # Advanced consumers (e.g., backfill jobs) may require direct SQLAlchemy access.
    def session_scope(self):
        return self._session()
