"""Utility to validate RSS feeds in RSS_FEEDS_EXTENDED by sampling recent articles.

Run as a standalone module:
    python -m newsbot.feed_validator [--categories tech,science] [--limit 4]
"""

from __future__ import annotations

import argparse
import logging
import math
from typing import Iterable, List, Tuple

import feedparser

from newsbot.cleaner import clean_html
from newsbot.rss_feeds import RSS_FEEDS_EXTENDED

LOGGER = logging.getLogger("newsbot.feed_validator")
DEFAULT_ARTICLES_PER_FEED = 5
DEFAULT_FULL_TEXT_THRESHOLD = 900  # characters
SUMMARY_RATIO_THRESHOLD = 1.35  # content must exceed summary by this factor to count as full


class FeedEntrySummary:
    """Holds summary metrics for a single RSS entry."""

    __slots__ = (
        "title",
        "link",
        "published",
        "content_length",
        "summary_length",
        "is_full_text",
    )

    def __init__(
        self,
        title: str,
        link: str,
        published: str,
        content_length: int,
        summary_length: int,
        is_full_text: bool,
    ) -> None:
        self.title = title
        self.link = link
        self.published = published
        self.content_length = content_length
        self.summary_length = summary_length
        self.is_full_text = is_full_text


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate RSS feeds and report content richness.")
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated list of categories to sample (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_ARTICLES_PER_FEED,
        help="Maximum number of articles to inspect per feed (default: %(default)s)",
    )
    parser.add_argument(
        "--full-threshold",
        type=int,
        default=DEFAULT_FULL_TEXT_THRESHOLD,
        help="Minimum cleaned content length to consider entry full-text (default: %(default)s chars)",
    )
    parser.add_argument(
        "--ratio-threshold",
        type=float,
        default=SUMMARY_RATIO_THRESHOLD,
        help="Factor by which content must exceed summary length to be full-text (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-bozo",
        action="store_true",
        help="Skip feeds raising feedparser bozo exceptions instead of logging them",
    )
    return parser.parse_args()


def iter_categories(selected: Iterable[str] | None) -> Iterable[Tuple[str, List[str]]]:
    if selected is None:
        for category, feeds in RSS_FEEDS_EXTENDED.items():
            yield category, feeds
        return

    selected_set = {name.strip() for name in selected if name.strip()}
    for category in selected_set:
        feeds = RSS_FEEDS_EXTENDED.get(category)
        if not feeds:
            LOGGER.warning("Category '%s' not found in RSS_FEEDS_EXTENDED", category)
            continue
        yield category, feeds


def extract_content(entry) -> Tuple[str, str]:
    fragments: List[str] = []
    for content in entry.get("content", []) or []:
        value = content.get("value")
        if value:
            fragments.append(value)

    content_raw = "\n".join(fragments).strip()
    if not content_raw:
        content_raw = entry.get("summary", entry.get("description", "")) or ""

    summary_raw = entry.get("summary", entry.get("description", "")) or ""
    return clean_html(content_raw), clean_html(summary_raw)


def summarize_entry(
    entry,
    full_threshold: int,
    ratio_threshold: float,
) -> FeedEntrySummary:
    cleaned_content, cleaned_summary = extract_content(entry)
    content_length = len(cleaned_content)
    summary_length = len(cleaned_summary)

    length_ok = content_length >= full_threshold
    ratio_ok = summary_length == 0 or content_length >= summary_length * ratio_threshold
    is_full_text = bool(length_ok and ratio_ok)

    return FeedEntrySummary(
        title=(entry.get("title") or "<no title>").strip(),
        link=(entry.get("link") or "").strip(),
        published=(entry.get("published") or entry.get("updated") or "").strip(),
        content_length=content_length,
        summary_length=summary_length,
        is_full_text=is_full_text,
    )


def process_feed(
    feed_url: str,
    category: str,
    article_limit: int,
    full_threshold: int,
    ratio_threshold: float,
    skip_bozo: bool,
) -> List[FeedEntrySummary]:
    LOGGER.info("Fetching %s feed: %s", category, feed_url)
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:  # pragma: no cover - network/parse errors
        LOGGER.error("Failed to parse feed %s (%s): %s", feed_url, category, exc)
        return []

    if parsed.bozo and not skip_bozo:
        LOGGER.warning("Feed parsing bozo warning for %s: %s", feed_url, parsed.bozo_exception)

    entries = parsed.entries[:article_limit]
    summaries: List[FeedEntrySummary] = []
    for entry in entries:
        try:
            summary = summarize_entry(entry, full_threshold, ratio_threshold)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.error("Error summarizing entry from %s: %s", feed_url, exc)
            continue
        summaries.append(summary)
    return summaries


def feed_fullness_label(summaries: List[FeedEntrySummary]) -> str:
    if not summaries:
        return "NO_DATA"
    full_count = sum(1 for s in summaries if s.is_full_text)
    ratio = full_count / len(summaries)
    if ratio >= 0.6:
        return "LIKELY_FULL_TEXT"
    if ratio >= 0.3:
        return "MIXED"
    return "LIKELY_SUMMARY"


def main() -> None:  # pragma: no cover - runtime script
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)5s | %(message)s",
    )

    args = parse_arguments()
    selected = args.categories.split(",") if args.categories else None

    total_feeds = 0
    for category, feed_list in iter_categories(selected):
        LOGGER.info("\n===== Category: %s (feeds: %d) =====", category, len(feed_list))
        for feed_url in feed_list:
            total_feeds += 1
            summaries = process_feed(
                feed_url=feed_url,
                category=category,
                article_limit=args.limit,
                full_threshold=args.full_threshold,
                ratio_threshold=args.ratio_threshold,
                skip_bozo=args.skip_bozo,
            )

            label = feed_fullness_label(summaries)
            print(f"\nFeed: {feed_url}\n  Classification: {label} | Articles inspected: {len(summaries)}")
            for idx, summary in enumerate(summaries, start=1):
                status = "FULL" if summary.is_full_text else "SUMMARY"
                length_info = (
                    f"content_len={summary.content_length}"
                    f", summary_len={summary.summary_length}"
                )
                print(
                    f"    [{idx}] {summary.title}\n"
                    f"        Status: {status} | {length_info}\n"
                    f"        Link: {summary.link or '<no link>'}\n"
                    f"        Published: {summary.published or '<unknown>'}"
                )

    LOGGER.info("\nValidation run complete. Feeds inspected: %d", total_feeds)


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
