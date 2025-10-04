"""Controlled smoke test for RSS_FEEDS_EXTENDED ingestion.

This script fetches a small batch of articles from the extended feed registry,
ensures full-content enrichment, and prints summary statistics that confirm
science and health categories are being ingested successfully while broken feeds
are skipped automatically.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, Tuple

from sqlalchemy import func, select

from newsbot.feed_policies import build_feed_registry
from newsbot.main import collect_and_store_articles
from newsbot.models import Article as ArticleModel
from newsbot.storage import NewsStorage

# Configure a dedicated logger for the smoke test run
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("extended_feed_smoke")

# Limit categories and entries to keep the run small and focused
TARGET_CATEGORIES: Tuple[str, ...] = ("science", "health")
MAX_ENTRIES_PER_FEED: int = 5

def _summarize_database(storage: NewsStorage) -> Dict[str, Dict[str, int]]:
    """Gather database metrics after the smoke test completes.

    Returns a nested dictionary with total counts, full-content coverage, and
    per-category article tallies for quick inspection.
    """
    stats = defaultdict(dict)

    with storage.session_scope() as session:
        total_rows = session.execute(select(func.count(ArticleModel.id))).scalar_one()
        stats["database"]["total_articles"] = int(total_rows)

        full_count = session.execute(
            select(func.count(ArticleModel.id)).where(
                ArticleModel.full_content.is_not(None),
                func.length(func.trim(ArticleModel.full_content)) > 0,
            )
        ).scalar_one()
        stats["database"]["full_content_populated"] = int(full_count)

        category_rows = session.execute(
            select(ArticleModel.category, func.count(ArticleModel.id)).group_by(ArticleModel.category)
        ).all()
        for category, count in category_rows:
            stats["categories"][category or "(uncategorized)"] = int(count)

    return stats


def main() -> None:
    """Run the controlled fetch + enrichment workflow using extended feeds."""
    # Build a registry that leverages the extended feed catalogue while retaining
    # allow/deny list prioritization logic. This respects production filtering
    # without mutating the global RSS_FEEDS mapping.
    feed_registry = build_feed_registry(
        categories=TARGET_CATEGORIES,
        use_extended=True,
        allowlist_only=False,
    )

    logger.info("Extended registry assembled: %s", {k: len(v) for k, v in feed_registry.items()})

    # Execute the pipeline with bozo skipping and entry limits to mirror
    # a --skip-bozo controlled run. return_stats=True gives us detailed counters
    # for produced, enriched, and skipped feeds without querying internals.
    pipeline_stats = collect_and_store_articles(
        categories=TARGET_CATEGORIES,
        enrich_full=True,
        batch_enrich_limit=20,
        feed_registry=feed_registry,
        skip_bozo=True,
        max_entries_per_feed=MAX_ENTRIES_PER_FEED,
        return_stats=True,
    )

    feed_stats = pipeline_stats["feed_stats"]
    produced = feed_stats["total_articles"]
    post_dedup = sum(feed_stats["category_totals"].values())
    consumed = pipeline_stats["stored_articles"]
    enriched = pipeline_stats["full_fetch_success"]
    enrich_failed = pipeline_stats["full_fetch_failed"]
    bozo_skipped = feed_stats["bozo_skipped"]

    logger.info(
        "Run summary -> produced=%s post_dedup=%s consumed=%s enriched=%s failed_enrich=%s bozo_skipped=%s",
        produced,
        post_dedup,
        consumed,
        enriched,
        enrich_failed,
        bozo_skipped,
    )

    # Connect to the database to inspect stored totals and category distribution
    storage = NewsStorage()
    try:
        db_stats = _summarize_database(storage)
        logger.info("Database totals: %s", db_stats["database"])
        logger.info("Category counts: %s", {k: db_stats["categories"].get(k, 0) for k in TARGET_CATEGORIES})

        # Print a compact human-readable summary for science/health verification
        print("\n=== Extended Feed Smoke Test ===")
        print(f"Categories processed: {TARGET_CATEGORIES}")
        print(f"Feed entries per feed capped at: {MAX_ENTRIES_PER_FEED}")
        print(f"Feeds skipped (bozo): {bozo_skipped}")
        print(f"Messages produced: {produced}")
        print(f"Messages post-dedup: {post_dedup}")
        print(f"Messages consumed/stored: {consumed}")
        print(f"Successfully enriched (full_content fetched): {enriched}")
        print(f"Enrichment failures: {enrich_failed}")
        print("\nDatabase overview after run:")
        print(f"  Total articles: {db_stats['database']['total_articles']}")
        print(f"  With full_content: {db_stats['database']['full_content_populated']}")
        for category in TARGET_CATEGORIES:
            print(f"  {category} count: {db_stats['categories'].get(category, 0)}")
    finally:
        storage.close()


if __name__ == "__main__":  # pragma: no cover - manual verification entry point
    main()
