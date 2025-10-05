#!/usr/bin/env python3
"""
Simple test harness: ensure two articles exist in the DB and run the Qwen summarizer on them.

Usage: activate your conda env (news-env) and run:
    python scripts/test_two_articles_summarize.py

The script will print summaries for two articles using newsbot.llm_qwen.summarize_text.
"""
from __future__ import annotations

import os
import sys
import logging
from typing import List

# Ensure project root is on sys.path so `import newsbot` works when running as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from newsbot.storage import NewsStorage
from newsbot.llm_qwen import summarize_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_two_articles")


SAMPLE_ARTICLES = [
    {
        "title": "Breakthrough in renewable energy: new solar cell achieves 50% efficiency",
        "link": "https://example.com/articles/solar-50-efficiency",
        "publish_date": "2025-10-01T12:00:00Z",
        "source": "Example News",
        "category": "science",
        "content": (
            "Researchers have announced a prototype solar cell that reaches 50% efficiency under "
            "laboratory conditions. The breakthrough uses a novel multi-junction architecture and advanced "
            "materials engineering. Early tests indicate improved performance in low-light conditions, "
            "potentially lowering costs for large-scale deployment."
        ),
    },
    {
        "title": "Local startup raises $10M to build privacy-first search engine",
        "link": "https://example.com/articles/privacy-search-funding",
        "publish_date": "2025-09-27T08:30:00Z",
        "source": "Example Tech",
        "category": "tech",
        "content": (
            "A new startup focused on privacy-preserving web search announced a $10 million seed round. "
            "The company plans to combine on-device ranking signals with encrypted aggregations to avoid "
            "user profiling, and will launch a developer preview later this year. Investors cited rising "
            "demand for alternatives to surveillance-based search providers."
        ),
    },
]


def ensure_two_articles(storage: NewsStorage) -> List[int]:
    """Ensure at least two articles exist; insert sample articles if needed.

    Returns list of article IDs (at least two).
    """
    stats = storage.get_statistics()
    total = stats.get("total_articles", 0)
    logger.info("DB currently has %s articles", total)

    # If DB already has 2+ articles, fetch first two via fetch_articles_for_processing
    if total >= 2:
        rows = storage.fetch_articles_for_processing(limit=2, min_length=30)
        if len(rows) >= 2:
            return [r["article_id"] for r in rows[:2]]

    # Otherwise insert sample articles and then fetch them
    for art in SAMPLE_ARTICLES:
        inserted = storage.save_article(art)
        logger.info("Inserted sample article '%s': %s", art["title"], inserted)

    rows = storage.fetch_articles_for_processing(limit=2, min_length=30)
    return [r["article_id"] for r in rows[:2]]


def load_article_by_id(storage: NewsStorage, article_id: int) -> dict:
    # lightweight direct SQLAlchemy access via session_scope
    with storage.session_scope() as session:
        from newsbot.models import Article

        obj = session.get(Article, article_id)
        if obj is None:
            raise RuntimeError(f"Article id={article_id} not found")
        return {
            "id": obj.id,
            "title": obj.title,
            "link": obj.link,
            "content": obj.full_content or obj.content or "",
        }


def main():
    storage = NewsStorage()
    ids = ensure_two_articles(storage)
    logger.info("Using article ids: %s", ids)

    for aid in ids:
        art = load_article_by_id(storage, aid)
        text = art["content"]
        if not text or len(text.strip()) < 20:
            logger.warning("Article id=%s has insufficient text to summarize; skipping", aid)
            continue
        logger.info("Summarizing article id=%s title=%s", aid, art["title"])
        try:
            summary = summarize_text(text, max_tokens=120, temperature=0.2)
            print("---\nArticle:", art["title"])
            print("Summary:\n", summary)
        except Exception as exc:
            logger.error("Failed to summarize article id=%s: %s", aid, exc)


if __name__ == "__main__":
    main()
