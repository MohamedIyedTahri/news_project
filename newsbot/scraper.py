"""scraper.py - CLEAN IMPLEMENTATION WITH VPN INTEGRATION

Rebuilt clean version. Provides:
    * Pacing & retry with exponential backoff
    * Rotating user agents & optional proxy usage
    * Paywall / block heuristics + optional VPN rotation trigger
    * Main content extraction heuristics
    * Metrics for instrumentation
"""
from __future__ import annotations

import logging
import random
import time
import socket
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .cleaner import clean_html
from . import vpn

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Edge/123.0",
]

DEFAULT_TIMEOUT = 12
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.6
RANDOM_DELAY_RANGE = (2.0, 5.0)
CONNECT_ERRORS = (requests.ConnectionError, requests.Timeout, socket.timeout)
PAYWALL_KEYWORDS = ["paywall", "subscribe", "account required", "sign in", "subscriber-only"]

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

SCRAPER_METRICS = {
    "articles_requested": 0,
    "articles_fetched": 0,
    "articles_failed": 0,
    "blocked_403": 0,
    "vpn_rotations_attempted": 0,
    "vpn_rotations_triggered": 0,
}

@dataclass
class FetchedArticle:
    title: str
    link: str
    publish_date: str
    source: str
    category: str
    content: str
    raw_length: int
    cleaned_length: int
    fetch_status: str
    error: Optional[str] = None

def _choose_proxy(proxy_pool: Optional[List[str]]) -> Optional[Dict[str, str]]:
    if not proxy_pool:
        return None
    p = random.choice(proxy_pool)
    return {"http": p, "https": p}

def _human_delay(last_domain_times: Dict[str, float], domain: str):
    now = time.time()
    last = last_domain_times.get(domain, 0)
    target_gap = random.uniform(*RANDOM_DELAY_RANGE)
    elapsed = now - last
    remaining = target_gap - elapsed
    if remaining > 0:
        time.sleep(remaining)
    last_domain_times[domain] = time.time()

def _is_blocked_or_paywalled(status: int, snippet: str) -> bool:
    if status == 403:
        return True
    lower = snippet.lower()
    return any(k in lower for k in PAYWALL_KEYWORDS)

def fetch_single_article(url: str,
                         proxy_pool: Optional[List[str]] = None,
                         last_domain_times: Optional[Dict[str, float]] = None,
                         enable_vpn_rotation: bool = True) -> Optional[str]:
    last_domain_times = last_domain_times or {}
    domain = urlparse(url).netloc or "unknown-domain"
    consecutive_403 = 0
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        _human_delay(last_domain_times, domain)
        headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html,application/xhtml+xml"}
        proxies = _choose_proxy(proxy_pool)
        proxy_label = proxies['http'] if proxies else 'none'
        try:
            start = time.time()
            resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, allow_redirects=True, proxies=proxies)
            latency_ms = (time.time() - start) * 1000
            status = resp.status_code
            snippet = resp.text[:600]
            if status == 200 and not _is_blocked_or_paywalled(status, snippet):
                logger.info(f"Fetch success attempt={attempt} status=200 latency={latency_ms:.0f}ms proxy={proxy_label} url={url}")
                return resp.text
            else:
                if status == 403:
                    consecutive_403 += 1
                    SCRAPER_METRICS["blocked_403"] += 1
                last_error = f"HTTP {status}" if status >= 400 else "paywall heuristic"
                logger.warning(f"Fetch issue attempt={attempt} status={status} c403={consecutive_403} proxy={proxy_label} url={url}")
        except CONNECT_ERRORS as e:
            last_error = f"Connection error: {e}"
            logger.warning(f"Connection issue attempt={attempt} proxy={proxy_label} url={url} err={e}")
        except requests.RequestException as e:
            last_error = f"Request error: {e}"
            logger.warning(f"Request exception attempt={attempt} proxy={proxy_label} url={url} err={e}")

        if attempt < MAX_RETRIES:
            if enable_vpn_rotation and consecutive_403 >= 2:
                SCRAPER_METRICS["vpn_rotations_attempted"] += 1
                if vpn.rotate_vpn(reason="consecutive_403"):
                    SCRAPER_METRICS["vpn_rotations_triggered"] += 1
            sleep_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.2, 0.8)
            time.sleep(sleep_time)

    logger.error(f"Failed to fetch after {MAX_RETRIES} attempts url={url} last_error={last_error}")
    return None

def extract_main_content(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    for selector in CONTENT_CANDIDATES:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return clean_html(str(el))
    body = soup.body
    if body:
        return clean_html(str(body))
    return clean_html(html)

def fetch_full_articles(rss_articles_list: List[Dict],
                        proxy_pool: Optional[List[str]] = None,
                        enable_vpn_rotation: bool = True) -> Tuple[List[FetchedArticle], List[FetchedArticle]]:
    successful: List[FetchedArticle] = []
    failed: List[FetchedArticle] = []
    last_domain_times: Dict[str, float] = {}
    for art in rss_articles_list:
        SCRAPER_METRICS["articles_requested"] += 1
        url = art.get("link", "").strip()
        title = art.get("title", "").strip()
        if not url or not title:
            failed.append(FetchedArticle(
                title=title or "<missing>", link=url or "<missing>", publish_date=art.get("publish_date", ""),
                source=art.get("source", "Unknown"), category=art.get("category", "unknown"), content="",
                raw_length=0, cleaned_length=0, fetch_status="skipped", error="Missing title or URL"
            ))
            continue
        logger.info(f"Fetching full article: {title[:80]} ...")
        raw_html = fetch_single_article(url, proxy_pool=proxy_pool, last_domain_times=last_domain_times, enable_vpn_rotation=enable_vpn_rotation)
        if raw_html is None:
            SCRAPER_METRICS["articles_failed"] += 1
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
            SCRAPER_METRICS["articles_failed"] += 1
            failed.append(FetchedArticle(
                title=title, link=url, publish_date=art.get("publish_date", ""),
                source=art.get("source", "Unknown"), category=art.get("category", "unknown"), content="",
                raw_length=raw_length, cleaned_length=0, fetch_status="error", error="Empty content after extraction"
            ))
            continue
        SCRAPER_METRICS["articles_fetched"] += 1
        successful.append(FetchedArticle(
            title=title, link=url, publish_date=art.get("publish_date", ""), source=art.get("source", "Unknown"),
            category=art.get("category", "unknown"), content=cleaned, raw_length=raw_length,
            cleaned_length=cleaned_length, fetch_status="success"
        ))
    logger.info(f"Full article fetch summary: success={len(successful)} failed={len(failed)} total={len(rss_articles_list)}")
    return successful, failed

def enrich_and_store_full_articles(rss_articles: List[Dict], storage, deduplicator=None,
                                   proxy_pool: Optional[List[str]] = None,
                                   enable_vpn_rotation: bool = True) -> Dict[str, int]:
    full_ok, full_fail = fetch_full_articles(rss_articles, proxy_pool=proxy_pool, enable_vpn_rotation=enable_vpn_rotation)
    skipped_duplicate = 0
    if deduplicator:
        filtered = []
        for art in full_ok:
            mock = {"title": art.title, "link": art.link, "publish_date": art.publish_date, "source": art.source, "category": art.category, "content": art.content}
            if deduplicator.is_duplicate_url(art.link) or deduplicator.is_duplicate_content(mock, []):
                skipped_duplicate += 1
                continue
            filtered.append(art)
        full_ok = filtered
    saved = 0
    for art in full_ok:
        if storage.save_article({
            "title": art.title,
            "link": art.link,
            "publish_date": art.publish_date,
            "source": art.source,
            "category": art.category,
            "content": art.content,
            "full_content": art.content,
        }):
            saved += 1
    stats = {
        "requested": len(rss_articles),
        "fetched_full": len(full_ok),
        "failed_full": len(full_fail),
        "saved": saved,
        "skipped_duplicates": skipped_duplicate,
        "metrics": SCRAPER_METRICS.copy(),
    }
    logger.info(f"Full article enrichment stats: {stats}")
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = [{
        "title": "Example Article",
        "link": "https://example.com",
        "publish_date": "2025-09-29",
        "source": "Example Source",
        "category": "test",
        "content": "Short summary"
    }]
    ok, fail = fetch_full_articles(sample, enable_vpn_rotation=False)
    print({"ok": len(ok), "fail": len(fail), "metrics": SCRAPER_METRICS})
