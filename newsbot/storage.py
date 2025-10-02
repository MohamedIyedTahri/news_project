import sqlite3
import os
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = "news_articles.db"

logger = logging.getLogger(__name__)


class NewsStorage:
    def __init__(self, db_path=DB_PATH):
        # Allow row factory for potential dict-like access
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")  # better concurrent reads
        self.create_table()
        self._migrate_add_full_content()
        self._ensure_processed_articles_table()

    def create_table(self):
        """Create base table if it does not exist (initial schema)."""
        self.conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                link TEXT UNIQUE,
                publish_date TEXT,
                source TEXT,
                category TEXT,
                content TEXT
            )
            '''
        )
        self.conn.commit()

    # --- Schema Migration Helpers -------------------------------------------------
    def _column_exists(self, table: str, column: str) -> bool:
        cur = self.conn.execute(f"PRAGMA table_info({table})")
        for row in cur.fetchall():
            if row[1] == column:
                return True
        return False

    def _migrate_add_full_content(self):
        """Add full_content column if missing.

        Safely performs idempotent schema migration by checking for column first.
        """
        try:
            if not self._column_exists("articles", "full_content"):
                logger.info("Applying migration: adding 'full_content' column to articles table")
                self.conn.execute("ALTER TABLE articles ADD COLUMN full_content TEXT")
                self.conn.commit()
            else:
                logger.debug("Migration skip: 'full_content' column already present")
        except Exception as e:
            logger.error(f"Migration error (add full_content): {e}")

    def _ensure_processed_articles_table(self):
        """Create processed_articles table for Spark features if missing."""
        try:
            self.conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS processed_articles (
                    article_id INTEGER PRIMARY KEY,
                    token_count INTEGER,
                    tokens TEXT,
                    feature_vector TEXT,
                    pipeline_version TEXT,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(article_id) REFERENCES articles(id)
                )
                '''
            )
            self.conn.commit()
            # Lightweight index for faster lookups by processed timestamp
            self.conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_processed_articles_processed_at
                ON processed_articles (processed_at)
                '''
            )
            self.conn.commit()
        except Exception as exc:
            logger.error(f"Failed to ensure processed_articles table: {exc}")

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
        try:
            cursor = self.conn.execute(
                '''
                INSERT OR IGNORE INTO articles (title, link, publish_date, source, category, content, full_content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    article["title"],
                    article["link"],
                    article["publish_date"],
                    article["source"],
                    article["category"],
                    article["content"],
                    article.get("full_content")
                ),
            )
            inserted = cursor.rowcount > 0

            # If not inserted (duplicate link) and we have new full_content, try updating only if missing
            if not inserted and article.get("full_content"):
                self.conn.execute(
                    '''
                    UPDATE articles
                    SET full_content = ?
                    WHERE link = ? AND (full_content IS NULL OR length(full_content)=0)
                    ''',
                    (article.get("full_content"), article["link"]),
                )
            self.conn.commit()
            return inserted
        except Exception as e:
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
        processed_at = processed_at or datetime.utcnow().isoformat(timespec="seconds")
        try:
            self.conn.execute(
                '''
                INSERT INTO processed_articles (article_id, token_count, tokens, feature_vector, pipeline_version, processed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    token_count = excluded.token_count,
                    tokens = excluded.tokens,
                    feature_vector = excluded.feature_vector,
                    pipeline_version = excluded.pipeline_version,
                    processed_at = excluded.processed_at
                ''',
                (
                    article_id,
                    token_count,
                    json.dumps(tokens),
                    json.dumps(feature_vector),
                    pipeline_version,
                    processed_at,
                ),
            )
            self.conn.commit()
            return True
        except Exception as exc:
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
        content_expr = (
            "COALESCE(NULLIF(full_content, ''), NULLIF(content, ''))"
            if prefer_full_content
            else "COALESCE(NULLIF(content, ''), NULLIF(full_content, ''))"
        )

        query = [
            "SELECT id, {expr} AS clean_text FROM articles WHERE {expr} IS NOT NULL".format(expr=content_expr)
        ]
        params: List[Any] = []

        # Apply minimum content length filter
        query.append(f"AND length(trim({content_expr})) >= ?")
        params.append(min_length)

        if since_id is not None:
            query.append("AND id > ?")
            params.append(since_id)

        query.append("ORDER BY id ASC")
        if limit is not None:
            query.append("LIMIT ?")
            params.append(limit)

        final_query = "\n".join(query)
        try:
            cursor = self.conn.execute(final_query, tuple(params))
            rows = cursor.fetchall()
            return [{"article_id": row[0], "clean_text": row[1]} for row in rows if row[1]]
        except Exception as exc:
            logger.error(f"Error fetching articles for processing: {exc}")
            return []

    def get_latest_processed_article_id(self) -> int:
        """Return the highest article id already processed by Spark."""
        try:
            cursor = self.conn.execute("SELECT COALESCE(MAX(article_id), 0) FROM processed_articles")
            value = cursor.fetchone()[0]
            return int(value or 0)
        except Exception as exc:
            logger.error(f"Error retrieving latest processed article id: {exc}")
            return 0

    def get_statistics(self):
        """
        Get database statistics.
        
        Returns:
            dict: Statistics about stored articles
        """
        try:
            # Total articles
            cursor = self.conn.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            # Articles by category
            cursor = self.conn.execute("SELECT category, COUNT(*) FROM articles GROUP BY category")
            by_category = dict(cursor.fetchall())
            
            # Articles by source
            cursor = self.conn.execute("SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10")
            by_source = dict(cursor.fetchall())
            
            return {
                'total_articles': total_articles,
                'by_category': by_category,
                'top_sources': by_source
            }
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}

    def close(self):
        self.conn.close()
