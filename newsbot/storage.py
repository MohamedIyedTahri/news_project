import sqlite3
import os

DB_PATH = "news_articles.db"

class NewsStorage:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                link TEXT UNIQUE,
                publish_date TEXT,
                source TEXT,
                category TEXT,
                content TEXT
            )
        ''')
        self.conn.commit()

    def save_article(self, article):
        """
        Save an article to the database.
        
        Args:
            article (dict): Article dictionary with required fields
            
        Returns:
            bool: True if article was saved successfully, False otherwise
        """
        try:
            cursor = self.conn.execute('''
                INSERT OR IGNORE INTO articles (title, link, publish_date, source, category, content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                article["title"],
                article["link"],
                article["publish_date"],
                article["source"],
                article["category"],
                article["content"]
            ))
            self.conn.commit()
            return cursor.rowcount > 0  # Return True if a new row was inserted
        except Exception as e:
            print(f"Error saving article: {e}")
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
