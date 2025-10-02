# News Dataset Summary Report

_Last updated: 2025-09-29_

## 1. Data Source Catalog

The ingestion pipeline draws on curated RSS feeds grouped by topic. Counts below reflect active entries in `newsbot/rss_feeds.py` (primary registry); the extended catalog adds optional categories for higher-volume runs.

| Category | Feed Count | Representative Publishers | Notes |
| --- | --- | --- | --- |
| International | 11 | BBC World, Reuters, The Guardian, Al Jazeera English | Mix of summary and full-text feeds for global coverage. |
| Technology | 11 | Ars Technica, The Verge, TechCrunch, VentureBeat | Heavy rotation of consumer tech and startup outlets; several full-text WordPress feeds. |
| Finance | 12 | Wall Street Journal (Markets), Financial Times, Bloomberg, Federal Reserve | Balances market wire services with regulatory releases. |
| Arabic | 12 | الجزيرة (Al Jazeera Arabic), العربية (Al Arabiya), CNN Arabic, Asharq | Prioritizes MENA-focused reporting; a subset delivers full Arabic content. |
| Science | 8 | NASA, ScienceDaily, Scientific American, Space.com | Science portals plus institutional announcements. |
| Health | 8 | WHO, NIH, Harvard Health, Stat News | Clinical news blended with public-health alerts. |

Optional extended categories (disabled by default) add `sports` (5 feeds) and `entertainment` (4 feeds) along with annotations describing whether each feed serves full text or summaries. These can be toggled by passing `feed_registry=RSS_FEEDS_EXTENDED` to the collector.

## 2. Acquisition & Processing Strategy

The end-to-end flow is implemented in `newsbot/main.py` and supporting modules:

1. **RSS harvesting** (`fetch_multiple_feeds`)
   - Uses `feedparser` to iterate each category's feed list.
   - Normalizes essential fields (title, link, publish date, source, category, summary content) after HTML cleaning via `cleaner.clean_html`.
   - Optional `max_entries_per_feed` guard and `skip_bozo` flag allow controlled runs and graceful handling of malformed feeds.

2. **In-memory deduplication** (`deduplicator.ArticleDeduplicator`)
   - Tracks seen URLs and hashes of title/summary pairs.
   - Applies fuzzy title matching (SequenceMatcher, threshold 0.85) to collapse near-duplicates emitted across partner sites or mirrored feeds.

3. **Persistent storage** (`storage.NewsStorage`)
   - Inserts into SQLite (`news_articles.db`) with `INSERT OR IGNORE` on the canonical `link` column.
   - Auto-migrates the schema to include a `full_content` column and updates existing rows when fresh full text is available.
   - Provides `get_statistics()` for downstream monitoring.

4. **Full article enrichment** (`scraper.fetch_full_articles`, `enrich_database_with_full_articles`)
   - Fetches full HTML with retry/backoff, rotating user agents, and optional VPN hooks (`newsbot/vpn.py`).
   - Extracts core article body using heuristic selectors followed by HTML stripping.
   - Immediately attempts to attach full content before insertion; a secondary backfill (`enrich_database_with_full_articles`) targets older rows lacking full text.

5. **Hooks for downstream NLP** (`hooks.py`)
   - Placeholder functions for language detection, sentiment, category refinement, and chunking supply future-proof integration points for RAG/embedding pipelines.

Operationally, the producer/consumer automation (`scripts/automated_pipeline.py`) batches these steps, and the deduplication + `INSERT OR IGNORE` safeguards prevent inflated counts when the consumer lags behind the producer.

## 3. Database Snapshots (2025-09-29)

Statistics captured by running the active virtual environment (`.venv`) with the existing SQLite store:

- **Total articles:** 1,017
- **Category distribution:**
  - Arabic: 110
  - Finance: 107
  - Health: 5
  - International: 361
  - Science: 20
  - Tech: 414
- **Top sources by volume (top 10):** Engadget (150), The Guardian World (136), Al Jazeera English (106), WIRED (105), BBC News (88), Latest News aggregation (73), CNN Arabic (63), France24 Arabic (47), The Verge (44), Stock Market News (41).
- **Full-content coverage:** 62% of stored rows (628 / 1,017) currently hold enriched full text; 389 remain summary-only. The backfill task continues to improve this ratio during longer runs.
- **Date range:** Earliest stored publish timestamp: 2025-09-27T12:09:15-04:00. Latest (string-sorted) timestamp: Wed, 25 Jan 2023 19:52:00 +0000. Because publish dates are stored as feed-provided strings, lexicographic ordering can surface older records as "latest"; normalizing to ISO datetimes is earmarked for a future migration.

## 4. Observations & Next Steps

- **Consumer throughput:** Recent diagnostics showed the Kafka consumer capped at 50 messages per cycle, allowing the backlog to accumulate while deduplication filtered out repeat links. Raising the cap or draining the backlog with a one-time high `--max-messages` run will surface more unique inserts.
- **Schema normalization:** Converting `publish_date` to an ISO timestamp column would improve chronological queries and resolve the mixed-format ordering noted above.
- **Coverage gaps:** Health, science, and Arabic categories have fewer full-text sources relative to tech and international feeds. Consider augmenting those pools with more full-article providers or enabling the extended catalog for additional volume.

This report will be updated as new feeds are added or the enrichment coverage changes. For regeneration, rerun `python -m newsbot.main` or the automation pipeline, then execute the same SQLite summary snippets to refresh the metrics section.
