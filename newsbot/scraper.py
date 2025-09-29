"""scraper.py

Module to fetch full article content from URLs obtained via RSS feeds.

Features:
- Graceful HTTP fetching with timeouts, retries, and user-agent rotation
- HTML cleaning (reuses cleaner.clean_html)
- Basic main-content extraction heuristics (article tags, common content divs)
- Integration point for deduplication (content hashing before save)
- Structured logging for success/failure

Future Extensions:
- Async fetching via httpx / asyncio
- Boilerplate / navigation removal via readability-lxml or trafilatura (optional)
- Language detection, summarization, embedding preparation
"""
from __future__ import annotations

import logging
import time
import random
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from newsbot.cleaner import clean_html

# Configure a module-level logger
logger = logging.getLogger(__name__)

# Default headers (rotate user-agents lightly to avoid naive blocking)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/125.0"
]

DEFAULT_TIMEOUT = 10  # seconds
MAX_RETRIES = 2
RETRY_BACKOFF = 1.5  # exponential backoff multiplier

# Common CSS selectors / tag candidates for article main content
CONTENT_CANDIDATES = [
    "article",
    "div.article-body",
    "div.article__content",
    "div#article-body",
    "div.post-content",
    "div.entry-content",
    "section.article-body",
    "div#content",
    "main",
]

@dataclass
class FetchedArticle:
    """Represents a fully fetched & cleaned article ready for storage."""
    title: str
    link: str
    publish_date: str
    source: str
    category: str
    content: str
    raw_length: int
    cleaned_length: int
    fetch_status: str  # success | skipped | error
    error: Optional[str] = None


def _hash_content_snippet(text: str) -> str:
    snippet = text[:500].lower().strip()
    return hashlib.md5(snippet.encode("utf-8")).hexdigest()


def fetch_single_article(url: str) -> Optional[str]:
    """Fetch raw HTML for a single article URL with retries.

    Returns raw HTML string or None on failure.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):  # initial + retries
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}"
                logger.warning(f"Fetch attempt {attempt} for {url} failed: {last_error}")
            else:
                return resp.text
        except requests.RequestException as e:
            last_error = str(e)
            logger.warning(f"Fetch attempt {attempt} for {url} raised exception: {e}")
        # Backoff before next attempt
        if attempt <= MAX_RETRIES:
            sleep_for = RETRY_BACKOFF ** attempt + random.uniform(0, 0.5)
            time.sleep(sleep_for)
    logger.error(f"Failed to fetch {url} after {MAX_RETRIES + 1} attempts: {last_error}")
    return None


def extract_main_content(html: str) -> str:
    """Extract main textual content from article HTML using heuristic selectors.

    Falls back to full-page text if targeted extraction fails.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style early
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    # Try structured candidates
    for selector in CONTENT_CANDIDATES:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return clean_html(str(el))

    # Fallback: body text
    body = soup.body
    if body:
        return clean_html(str(body))
    return clean_html(html)


def fetch_full_articles(rss_articles_list: List[Dict]) -> Tuple[List[FetchedArticle], List[FetchedArticle]]:
    """Fetch and clean full content for a list of RSS-parsed article dicts.

    Args:
        rss_articles_list: List of article dicts produced by fetch_rss_feed (title, link, publish_date, source, category, content(summary))

    Returns:
        (successful, failed) lists of FetchedArticle objects.
    """
    successful: List[FetchedArticle] = []
    failed: List[FetchedArticle] = []

    for art in rss_articles_list:
        url = art.get("link", "").strip()
        title = art.get("title", "").strip()
        if not url or not title:
            logger.debug("Skipping article with missing title or URL")
            failed.append(FetchedArticle(
                title=title or "<missing>", link=url or "<missing>", publish_date=art.get("publish_date", ""),
                source=art.get("source", "Unknown"), category=art.get("category", "unknown"), content="",
                raw_length=0, cleaned_length=0, fetch_status="skipped", error="Missing title or URL"
            ))
            continue

        logger.info(f"Fetching full article: {title[:80]}...")
        raw_html = fetch_single_article(url)
        if raw_html is None:
            failed.append(FetchedArticle(
                title=title, link=url, publish_date=art.get("publish_date", ""),
                source=art.get("source", "Unknown"), category=art.get("category", "unknown"), content="",
                raw_length=0, cleaned_length=0, fetch_status="error", error="Fetch failed"
            ))
            continue

        raw_length = len(raw_html)
        extracted = extract_main_content(raw_html)
        cleaned = extracted.strip()
        cleaned_length = len(cleaned)

        if cleaned_length == 0:
            failed.append(FetchedArticle(
                title=title, link=url, publish_date=art.get("publish_date", ""),
                source=art.get("source", "Unknown"), category=art.get("category", "unknown"), content="",
                raw_length=raw_length, cleaned_length=0, fetch_status="error", error="Empty content after extraction"
            ))
            continue

        successful.append(FetchedArticle(
            title=title,
            link=url,
            publish_date=art.get("publish_date", ""),
            source=art.get("source", "Unknown"),
            category=art.get("category", "unknown"),
            content=cleaned,
            raw_length=raw_length,
            cleaned_length=cleaned_length,
            fetch_status="success"
        ))

    logger.info(f"Full article fetch summary: success={len(successful)} failed={len(failed)} total={len(rss_articles_list)}")
    return successful, failed


# Example integration helper
def enrich_and_store_full_articles(rss_articles: List[Dict], storage, deduplicator=None) -> Dict[str, int]:
    """Fetch full content, optionally deduplicate, and store in DB.

    Args:
        rss_articles: Articles from RSS parsing phase.
        storage: Instance of NewsStorage.
        deduplicator: Optional ArticleDeduplicator for additional dedupe.

    Returns:
        Stats dict.
    """
    full_ok, full_fail = fetch_full_articles(rss_articles)

    saved = 0
    skipped_duplicate = 0

    # If deduplicator provided, run content-level duplication before save
    if deduplicator:
        filtered = []
        for art in full_ok:
            mock_dict = {
                "title": art.title,
                "link": art.link,
                "publish_date": art.publish_date,
                "source": art.source,
                "category": art.category,
                "content": art.content,
            }
            if deduplicator.is_duplicate_url(art.link) or deduplicator.is_duplicate_content(mock_dict, []):
                skipped_duplicate += 1
                continue
            filtered.append(art)
        full_ok = filtered

    for art in full_ok:
        saved |= storage.save_article({
            "title": art.title,
            "link": art.link,
            "publish_date": art.publish_date,
            "source": art.source,
            "category": art.category,
            "content": art.content,
        })
        if saved:
            saved += 1

    stats = {
        "requested": len(rss_articles),
        "fetched_full": len(full_ok),
        "failed_full": len(full_fail),
        "saved": saved,
        "skipped_duplicates": skipped_duplicate,
    }
    logger.info(f"Full article enrichment stats: {stats}")
    return stats

if __name__ == "__main__":  # Simple manual test scaffold
    import json
    logging.basicConfig(level=logging.INFO)
    sample = [{
        "title": "Example Article",
        "link": "https://example.com",
        "publish_date": "2025-09-29",
        "source": "Example Source",
        "category": "test",
        "content": "Short summary"
    }]
    success, failure = fetch_full_articles(sample)
    print(json.dumps({
        "success_count": len(success),
        "fail_count": len(failure)
    }, indent=2))
