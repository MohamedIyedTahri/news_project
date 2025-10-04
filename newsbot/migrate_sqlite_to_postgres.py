"""Utility to migrate existing SQLite data into the PostgreSQL backend.

This script reads the legacy ``news_articles.db`` SQLite file and replays its
contents into the configured PostgreSQL database using the SQLAlchemy ORM
models.  It is idempotent: rows are inserted if they do not yet exist based on
their unique ``link`` field, and updated otherwise.

Usage (examples)::

    python -m newsbot.migrate_sqlite_to_postgres --sqlite-path news_articles.db
    python -m newsbot.migrate_sqlite_to_postgres --database-url postgresql+psycopg2://user:pass@host/db

The PostgreSQL connection information defaults to the same environment variables
used by the runtime (``POSTGRES_HOST``, ``POSTGRES_PORT`` …) when
``--database-url`` is omitted.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, List, Optional

from sqlalchemy import select, text

from .db import get_session_factory
from .models import Article, FullContentStatus, ProcessedArticle

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass
class SQLiteArticleRow:
    id: int
    title: str
    link: str
    publish_date: Optional[str]
    source: Optional[str]
    category: Optional[str]
    content: Optional[str]
    full_content: Optional[str]
    full_content_status: Optional[str]


@dataclass
class SQLiteProcessedRow:
    article_id: int
    token_count: int
    tokens: str
    feature_vector: str
    pipeline_version: str
    processed_at: Optional[str]


def iter_sqlite_articles(sqlite_path: str, batch_size: int) -> Iterator[List[SQLiteArticleRow]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Detect optional columns
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(articles)")}
    has_status = "full_content_status" in columns

    select_columns = [
        "id",
        "title",
        "link",
        "publish_date",
        "source",
        "category",
        "content",
        "full_content",
    ]
    if has_status:
        select_columns.append("full_content_status")

    query = f"SELECT {', '.join(select_columns)} FROM articles ORDER BY id"
    cursor.execute(query)

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield [
            SQLiteArticleRow(
                id=row["id"],
                title=row["title"],
                link=row["link"],
                publish_date=row["publish_date"],
                source=row["source"],
                category=row["category"],
                content=row["content"],
                full_content=row["full_content"],
                full_content_status=row.get("full_content_status") if has_status else None,
            )
            for row in rows
        ]

    conn.close()


def iter_sqlite_processed(sqlite_path: str, batch_size: int) -> Iterator[List[SQLiteProcessedRow]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT article_id, token_count, tokens, feature_vector, pipeline_version, processed_at "
            "FROM processed_articles ORDER BY article_id"
        )
    except sqlite3.OperationalError:
        conn.close()
        return

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield [
            SQLiteProcessedRow(
                article_id=row["article_id"],
                token_count=row["token_count"],
                tokens=row["tokens"],
                feature_vector=row["feature_vector"],
                pipeline_version=row["pipeline_version"],
                processed_at=row["processed_at"],
            )
            for row in rows
        ]

    conn.close()


def _coerce_status(row: SQLiteArticleRow) -> Optional[FullContentStatus]:
    if row.full_content_status:
        try:
            return FullContentStatus(row.full_content_status)
        except ValueError:
            logger.warning("Unknown full_content_status '%s' for link=%s", row.full_content_status, row.link)
            return None
    if row.full_content:
        return FullContentStatus.SUCCESS
    return None


def migrate(sqlite_path: str, database_url: Optional[str], batch_size: int) -> None:
    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        engine = session.get_bind()
        logger.info("Migrating data from %s to %s", sqlite_path, engine.url)
        session.execute(text("SELECT 1"))
        session.commit()

    max_article_id = 0
    for batch in iter_sqlite_articles(sqlite_path, batch_size):
        with session_factory() as session:
            for row in batch:
                max_article_id = max(max_article_id, row.id)
                status = _coerce_status(row)
                existing: Article | None = session.execute(
                    select(Article).where(Article.link == row.link)
                ).scalar_one_or_none()
                if existing:
                    # Update fields if missing
                    if not existing.full_content and row.full_content:
                        existing.full_content = row.full_content
                        existing.full_content_status = status
                    if not existing.content and row.content:
                        existing.content = row.content
                    continue

                article = Article(
                    id=row.id,
                    title=row.title,
                    link=row.link,
                    publish_date=row.publish_date,
                    source=row.source,
                    category=row.category,
                    content=row.content,
                    full_content=row.full_content,
                    full_content_status=status,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(article)
            session.commit()

    # Sync processed articles
    for batch in iter_sqlite_processed(sqlite_path, batch_size):
        with session_factory() as session:
            for row in batch:
                existing = session.get(ProcessedArticle, row.article_id)
                if existing:
                    continue
                processed_dt = None
                if row.processed_at:
                    try:
                        processed_dt = datetime.fromisoformat(row.processed_at.replace("Z", ""))
                    except ValueError:
                        processed_dt = datetime.utcnow()
                else:
                    processed_dt = datetime.utcnow()
                processed = ProcessedArticle(
                    article_id=row.article_id,
                    token_count=row.token_count,
                    tokens=row.tokens,
                    feature_vector=row.feature_vector,
                    pipeline_version=row.pipeline_version,
                    processed_at=processed_dt,
                )
                session.add(processed)
            session.commit()

    with session_factory() as session:
        engine = session.get_bind()
        if max_article_id and engine.dialect.name == "postgresql":
            logger.info("Adjusting sequence for articles.id -> %s", max_article_id)
            session.execute(
                text("SELECT setval(pg_get_serial_sequence('articles','id'), :value, TRUE)"),
                {"value": max_article_id},
            )
            session.commit()

    logger.info("Migration complete.")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite data into PostgreSQL")
    parser.add_argument("--sqlite-path", default="news_articles.db", help="Path to the legacy SQLite database")
    parser.add_argument("--database-url", help="Target SQLAlchemy database URL (optional; defaults to env settings)")
    parser.add_argument("--batch-size", type=int, default=500, help="Number of rows to process per batch")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    migrate(args.sqlite_path, args.database_url, args.batch_size)


if __name__ == "__main__":  # pragma: no cover
    main()
