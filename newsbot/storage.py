import sqlite3
import os
import logging

DB_PATH = "news_articles.db"

logger = logging.getLogger(__name__)


class NewsStorage:
    def __init__(self, db_path=DB_PATH):
        # Allow row factory for potential dict-like access
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")  # better concurrent reads
        self.create_table()
        self._migrate_add_full_content()

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
