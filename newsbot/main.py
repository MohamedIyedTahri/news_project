import feedparser
import logging
from datetime import datetime
from newsbot.cleaner import clean_html
from newsbot.storage import NewsStorage
from newsbot.rss_feeds import RSS_FEEDS
from newsbot.deduplicator import ArticleDeduplicator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Step 1: Fetch and parse one RSS feed
def fetch_rss_feed(feed_url, category):
    """
    Fetch and parse articles from a single RSS feed.
    
    Args:
        feed_url (str): The URL of the RSS feed
        category (str): The category of the news (e.g., 'tech', 'international')
    
    Returns:
        list: List of article dictionaries
    """
    try:
        logger.info(f"Fetching RSS feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        # Check if feed was parsed successfully
        if feed.bozo:
            logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
        
        articles = []
        for entry in feed.entries:
            try:
                # Extract and clean article data
                article = {
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", "").strip(),
                    "publish_date": entry.get("published", "").strip(),
                    "source": feed.feed.get("title", "Unknown Source").strip(),
                    "category": category,
                    "content": clean_html(entry.get("summary", entry.get("description", "")))
                }
                
                # Only add articles with essential fields
                if article["title"] and article["link"]:
                    articles.append(article)
                else:
                    logger.warning(f"Skipping article with missing title or link")
                    
            except Exception as e:
                logger.error(f"Error processing article entry: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(articles)} articles from {feed_url}")
        return articles
        
    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_url}: {e}")
        return []

# Step 2: Fetch and parse multiple RSS feeds with deduplication
def fetch_multiple_feeds(feed_categories=None, use_deduplication=True):
    """
    Fetch and parse articles from multiple RSS feeds across different categories.
    
    Args:
        feed_categories (list): List of category names to fetch. If None, fetches all categories.
        use_deduplication (bool): Whether to apply deduplication logic
    
    Returns:
        dict: Dictionary with category names as keys and list of articles as values
    """
    if feed_categories is None:
        feed_categories = RSS_FEEDS.keys()
    
    all_articles = {}
    total_articles = 0
    total_duplicates = 0
    
    # Initialize deduplicator if requested
    deduplicator = ArticleDeduplicator() if use_deduplication else None
    
    for category in feed_categories:
        if category not in RSS_FEEDS:
            logger.warning(f"Category '{category}' not found in RSS_FEEDS")
            continue
        
        category_articles = []
        logger.info(f"Processing category: {category}")
        
        for feed_url in RSS_FEEDS[category]:
            articles = fetch_rss_feed(feed_url, category)
            category_articles.extend(articles)
            total_articles += len(articles)
        
        # Apply deduplication if enabled
        if use_deduplication and deduplicator:
            unique_articles, duplicate_count = deduplicator.deduplicate_articles(category_articles)
            category_articles = unique_articles
            total_duplicates += duplicate_count
            logger.info(f"Category '{category}': {len(unique_articles)} unique articles ({duplicate_count} duplicates removed)")
        else:
            logger.info(f"Category '{category}': {len(category_articles)} articles")
        
        all_articles[category] = category_articles
    
    logger.info(f"Total articles fetched: {total_articles}")
    if use_deduplication:
        logger.info(f"Total duplicates removed: {total_duplicates}")
    
    return all_articles

# Step 3: Save multiple articles with progress tracking
def save_articles_batch(articles_dict, storage):
    """
    Save articles from multiple categories to the database.
    
    Args:
        articles_dict (dict): Dictionary with categories and their articles
        storage (NewsStorage): Storage instance
    
    Returns:
        dict: Statistics about saved articles per category
    """
    stats = {}
    
    for category, articles in articles_dict.items():
        saved_count = 0
        for article in articles:
            if storage.save_article(article):
                saved_count += 1
        
        stats[category] = {
            'total': len(articles),
            'saved': saved_count,
            'duplicates': len(articles) - saved_count
        }
        
        logger.info(f"Category '{category}': {saved_count}/{len(articles)} articles saved")
    
    return stats

if __name__ == "__main__":
    try:
        storage = NewsStorage()
        
        # Option 1: Fetch one RSS feed (international)
        print("\n=== Testing Single RSS Feed ===")
        feed_url = RSS_FEEDS["international"][0]
        logger.info(f"Starting to fetch articles from: {feed_url}")
        articles = fetch_rss_feed(feed_url, "international")
        
        # Save articles to database
        saved_count = 0
        for article in articles:
            if storage.save_article(article):
                saved_count += 1
        
        print(f"✓ Single feed: Saved {saved_count} out of {len(articles)} articles")
        
        # Option 2: Fetch multiple RSS feeds with deduplication
        print("\n=== Testing Multiple RSS Feeds with Deduplication ===")
        # Test with specific categories first
        test_categories = ["tech", "international"]
        all_articles = fetch_multiple_feeds(test_categories, use_deduplication=True)
        
        # Save all articles
        stats = save_articles_batch(all_articles, storage)
        
        # Print summary
        total_saved = sum(s['saved'] for s in stats.values())
        total_articles = sum(s['total'] for s in stats.values())
        
        print(f"\n=== Summary ===")
        for category, stat in stats.items():
            print(f"{category}: {stat['saved']}/{stat['total']} saved ({stat['duplicates']} duplicates)")
        
        print(f"✓ Multiple feeds: Saved {total_saved} out of {total_articles} articles total")
        
        # Show database statistics
        print(f"\n=== Database Statistics ===")
        db_stats = storage.get_statistics()
        print(f"Total articles in database: {db_stats.get('total_articles', 0)}")
        print("Articles by category:")
        for cat, count in db_stats.get('by_category', {}).items():
            print(f"  {cat}: {count}")
        print("Top sources:")
        for source, count in list(db_stats.get('top_sources', {}).items())[:5]:
            print(f"  {source}: {count}")
        
        storage.close()
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        print(f"✗ Error: {e}")
    finally:
        if 'storage' in locals():
            storage.close()