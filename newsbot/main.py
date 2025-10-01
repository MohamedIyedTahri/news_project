import feedparser
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from newsbot.cleaner import clean_html
from newsbot.storage import NewsStorage
from newsbot.rss_feeds import RSS_FEEDS
from newsbot.deduplicator import ArticleDeduplicator
from newsbot.scraper import fetch_full_articles

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Step 1: Fetch and parse one RSS feed
def fetch_rss_feed(
    feed_url: str,
    category: str,
    *,
    skip_bozo: bool = False,
    max_entries: Optional[int] = None,
):
    """
    Fetch and parse articles from a single RSS feed.
    
    Args:
        feed_url (str): The URL of the RSS feed
        category (str): The category of the news (e.g., 'tech', 'international')
    
    Returns:
        tuple: (list of article dicts, bool indicating bozo skip)
    """
    skipped_due_to_bozo = False
    try:
        logger.info(f"Fetching RSS feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        # Check if feed was parsed successfully
        if feed.bozo:
            logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            if skip_bozo:
                # skip processing this feed entirely when --skip-bozo is active
                logger.info(f"Skipping feed due to bozo flag: {feed_url}")
                skipped_due_to_bozo = True
                return [], skipped_due_to_bozo
        
        articles = []
        # limit entries during controlled runs to avoid huge batches
        entries = feed.entries[:max_entries] if max_entries else feed.entries
        for entry in entries:
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
        return articles, skipped_due_to_bozo
        
    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_url}: {e}")
        return [], skipped_due_to_bozo

# Step 2: Fetch and parse multiple RSS feeds with deduplication
def fetch_multiple_feeds(
    feed_categories: Optional[Iterable[str]] = None,
    use_deduplication: bool = True,
    feed_registry: Optional[Dict[str, List[str]]] = None,
    skip_bozo: bool = False,
    max_entries_per_feed: Optional[int] = None,
    return_stats: bool = False,
):
    """
    Fetch and parse articles from multiple RSS feeds across different categories.
    
    Args:
        feed_categories (list): List of category names to fetch. If None, fetches all categories.
        use_deduplication (bool): Whether to apply deduplication logic
        feed_registry: Optional custom registry of feeds by category.
        skip_bozo: When True, skip feeds that fail parsing (feed.bozo set).
        max_entries_per_feed: Limit the number of entries pulled from each feed.
        return_stats: When True, also return a stats dictionary for monitoring.

    Returns:
        dict: Dictionary with category names as keys and list of articles as values.
        tuple: If return_stats is True, returns (articles_by_category, stats_dict).
    """
    registry = feed_registry or RSS_FEEDS

    if feed_categories is None:
        feed_categories = registry.keys()
    
    all_articles = {}
    category_post_counts: Dict[str, int] = {}
    total_articles = 0
    total_duplicates = 0
    bozo_skipped = 0
    
    # Initialize deduplicator if requested
    deduplicator = ArticleDeduplicator() if use_deduplication else None
    
    for category in feed_categories:
        if category not in registry:
            logger.warning(f"Category '{category}' not found in RSS_FEEDS")
            continue
        
        category_articles = []
        logger.info(f"Processing category: {category}")
        
        for feed_url in registry.get(category, []):
            articles, was_bozo_skip = fetch_rss_feed(
                feed_url,
                category,
                skip_bozo=skip_bozo,
                max_entries=max_entries_per_feed,
            )
            if was_bozo_skip:
                bozo_skipped += 1
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
        category_post_counts[category] = len(category_articles)
    
    logger.info(f"Total articles fetched: {total_articles}")
    if use_deduplication:
        logger.info(f"Total duplicates removed: {total_duplicates}")
    if skip_bozo:
        logger.info(f"Feeds skipped due to bozo flag: {bozo_skipped}")
    
    if return_stats:
        stats = {
            "total_articles": total_articles,
            "duplicates_removed": total_duplicates if use_deduplication else 0,
            "bozo_skipped": bozo_skipped,
            "category_totals": category_post_counts,
        }
        return all_articles, stats

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

# --------------------- Full Content Enrichment & Pipeline -------------------------
def enrich_database_with_full_articles(storage: NewsStorage, limit: int = 20, min_full_length: int = 800):
    """Backfill full_content for articles that only have summaries.

    Args:
        storage: Active NewsStorage instance.
        limit: Max number of articles to enrich in this run.
        min_full_length: Minimum length to consider fetched full content valid.
    """
    logger.info("Starting enrichment backfill for articles missing full_content")
    try:
        cursor = storage.conn.execute(
            """
            SELECT id, title, link, publish_date, source, category, content, full_content
            FROM articles
            WHERE (full_content IS NULL OR length(full_content)=0)
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        if not rows:
            logger.info("No articles require enrichment.")
            return {"requested": 0, "updated": 0}

        rss_style_articles = []
        for r in rows:
            rss_style_articles.append({
                "title": r[1],
                "link": r[2],
                "publish_date": r[3] or "",
                "source": r[4] or "Unknown",
                "category": r[5] or "uncategorized",
                "content": r[6] or "",
            })

        full_ok, full_fail = fetch_full_articles(rss_style_articles)
        updated = 0
        for art in full_ok:
            if len(art.content) < min_full_length:
                continue
            storage.conn.execute(
                "UPDATE articles SET full_content=? WHERE link=? AND (full_content IS NULL OR length(full_content)=0)",
                (art.content, art.link),
            )
            updated += 1
        storage.conn.commit()

        stats = {
            "requested": len(rss_style_articles),
            "fetched_full": len(full_ok),
            "failed_full": len(full_fail),
            "updated": updated,
        }
        logger.info(f"Enrichment backfill stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error during enrichment backfill: {e}")
        return {"requested": 0, "updated": 0, "error": str(e)}


def collect_and_store_articles(
    categories: Optional[Iterable[str]] = None,
    enrich_full: bool = True,
    batch_enrich_limit: int = 30,
    feed_registry: Optional[Dict[str, List[str]]] = None,
    skip_bozo: bool = False,
    max_entries_per_feed: Optional[int] = None,
    return_stats: bool = False,
):
    """High-level pipeline: fetch RSS summaries, optionally fetch full content, store both.

    If enrich_full is True, attempts to fetch full content immediately for new articles
    before insertion (best-effort). Full content is saved in 'full_content' column while
    RSS summary remains in 'content'.

    Args:
        categories: Iterable of category names to process; defaults to all categories.
        enrich_full: Whether to fetch full article content during ingestion.
        batch_enrich_limit: Max number of backlog articles to enrich after ingest.
    feed_registry: Optional mapping of categories to feed URLs overriding defaults.
    skip_bozo: If True, feeds marked bozo by feedparser are skipped.
    max_entries_per_feed: Limit number of entries retrieved from each feed.
    return_stats: When True, return pipeline statistics for reporting.
    """
    storage = NewsStorage()
    try:
        fetch_result = fetch_multiple_feeds(
            feed_categories=categories,
            use_deduplication=True,
            feed_registry=feed_registry,
            skip_bozo=skip_bozo,
            max_entries_per_feed=max_entries_per_feed,
            return_stats=return_stats,
        )
        if return_stats:
            articles_by_cat, feed_stats = fetch_result
        else:
            articles_by_cat = fetch_result
            feed_stats = None
        enrich_stats = None
        # Flatten new articles for optional full fetch
        if enrich_full:
            flat = []
            for cat_list in articles_by_cat.values():
                flat.extend(cat_list)
            full_ok, full_fail = fetch_full_articles(flat)
            full_map = {fa.link: fa for fa in full_ok}
        else:
            full_map = {}
            full_ok, full_fail = [], []

        total_saved = 0
        for category, articles in articles_by_cat.items():
            for art in articles:
                link = art.get("link")
                full_obj = full_map.get(link)
                if full_obj:
                    art["full_content"] = full_obj.content
                storage.save_article(art)
                total_saved += 1
        logger.info(f"Pipeline stored {total_saved} articles (summary + optional full content)")

        # Opportunistic backfill for older rows missing full_content
        if enrich_full:
            enrich_stats = enrich_database_with_full_articles(storage, limit=batch_enrich_limit)
            logger.info(f"Post-ingest backfill completed: {enrich_stats}")
        if return_stats:
            pipeline_stats = {
                "stored_articles": total_saved,
                "full_fetch_success": len(full_ok),
                "full_fetch_failed": len(full_fail),
                "feed_stats": feed_stats,
                "backfill": enrich_stats if enrich_full else None,
            }
            return pipeline_stats
        return True
    finally:
        storage.close()

if __name__ == "__main__":
    try:
        storage = NewsStorage()
        
        # Option 1: Fetch one RSS feed (international)
        print("\n=== Testing Single RSS Feed ===")
        feed_url = RSS_FEEDS["international"][0]
        logger.info(f"Starting to fetch articles from: {feed_url}")
        articles, _ = fetch_rss_feed(feed_url, "international")
        
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

        # === Full Article Enrichment Example ===
        print("\n=== Full Article Enrichment (First 5 Tech Articles) ===")
        tech_articles = all_articles.get('tech', [])[:5]
        if tech_articles:
            full_success, full_failed = fetch_full_articles(tech_articles)
            print(f"Fetched full content for {len(full_success)} articles, {len(full_failed)} failed.")
            # Show a preview of first enriched article
            if full_success:
                first = full_success[0]
                print(f"Title: {first.title}\nFull content preview: {first.content[:300]}...")
        else:
            print("No tech articles available for enrichment test.")

    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        print(f"✗ Error: {e}")
    finally:
        if 'storage' in locals():
            storage.close()