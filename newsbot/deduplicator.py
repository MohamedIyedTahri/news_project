import hashlib
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class ArticleDeduplicator:
    """
    Handles deduplication of news articles based on various criteria.
    """
    
    def __init__(self):
        self.seen_urls = set()
        self.seen_hashes = set()
        self.title_similarity_threshold = 0.85  # 85% similarity threshold
    
    def generate_content_hash(self, article):
        """
        Generate a hash based on title and first 200 characters of content.
        
        Args:
            article (dict): Article dictionary
            
        Returns:
            str: MD5 hash of the content
        """
        content_for_hash = (
            article.get("title", "").strip().lower() + 
            article.get("content", "")[:200].strip().lower()
        )
        return hashlib.md5(content_for_hash.encode('utf-8')).hexdigest()
    
    def calculate_title_similarity(self, title1, title2):
        """
        Calculate similarity between two titles using sequence matching.
        
        Args:
            title1 (str): First title
            title2 (str): Second title
            
        Returns:
            float: Similarity ratio between 0 and 1
        """
        return SequenceMatcher(None, title1.lower().strip(), title2.lower().strip()).ratio()
    
    def is_duplicate_url(self, url):
        """
        Check if URL has already been seen.
        
        Args:
            url (str): Article URL
            
        Returns:
            bool: True if URL is duplicate
        """
        if url in self.seen_urls:
            return True
        self.seen_urls.add(url)
        return False
    
    def is_duplicate_content(self, article, existing_articles=None):
        """
        Check if article content is duplicate based on hash and title similarity.
        
        Args:
            article (dict): Article to check
            existing_articles (list): List of existing articles to compare against
            
        Returns:
            bool: True if content is duplicate
        """
        # Check content hash
        content_hash = self.generate_content_hash(article)
        if content_hash in self.seen_hashes:
            logger.debug(f"Duplicate content hash found for: {article.get('title', '')[:50]}...")
            return True
        
        # Check title similarity against existing articles
        if existing_articles:
            current_title = article.get("title", "").strip()
            for existing_article in existing_articles:
                existing_title = existing_article.get("title", "").strip()
                if self.calculate_title_similarity(current_title, existing_title) >= self.title_similarity_threshold:
                    logger.debug(f"Similar title found: '{current_title[:50]}...' vs '{existing_title[:50]}...'")
                    return True
        
        self.seen_hashes.add(content_hash)
        return False
    
    def deduplicate_articles(self, articles):
        """
        Remove duplicates from a list of articles.
        
        Args:
            articles (list): List of article dictionaries
            
        Returns:
            tuple: (unique_articles, duplicate_count)
        """
        unique_articles = []
        duplicate_count = 0
        
        for article in articles:
            # Check URL duplication
            if self.is_duplicate_url(article.get("link", "")):
                duplicate_count += 1
                logger.debug(f"Duplicate URL: {article.get('link', '')}")
                continue
            
            # Check content duplication
            if self.is_duplicate_content(article, unique_articles):
                duplicate_count += 1
                continue
            
            unique_articles.append(article)
        
        logger.info(f"Deduplication: {len(unique_articles)} unique, {duplicate_count} duplicates removed")
        return unique_articles, duplicate_count
    
    def reset(self):
        """Reset the deduplicator state."""
        self.seen_urls.clear()
        self.seen_hashes.clear()