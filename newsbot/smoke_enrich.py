"""Smoke test for full_content enrichment.

Runs a minimal workflow:
 1. Select a couple of articles missing full_content.
 2. Attempt enrichment.
 3. Show before/after length comparison.

Usage:
  python -m newsbot.smoke_enrich
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from sqlalchemy import func, select

from newsbot.models import Article as ArticleModel
from newsbot.storage import NewsStorage
from newsbot.main import enrich_database_with_full_articles

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
def _fetch_sample_missing(storage: NewsStorage, limit: int = 2) -> List[Tuple[int, str, int]]:
    with storage.session_scope() as session:
        summary_len = func.length(func.coalesce(ArticleModel.content, "")).label("summary_len")
        rows = session.execute(
            select(ArticleModel.id, ArticleModel.link, summary_len)
            .where(
                (ArticleModel.full_content.is_(None))
                | (func.length(func.trim(ArticleModel.full_content)) == 0)
            )
            .order_by(ArticleModel.id.desc())
            .limit(limit)
        ).all()
    return [(row.id, row.link, row.summary_len) for row in rows]


def main():
    storage = NewsStorage()
    try:
        sample_before = _fetch_sample_missing(storage, limit=2)
        if not sample_before:
            print("No articles require enrichment (full_content already populated).")
            return
        print("Before enrichment:")
        for art_id, link, summary_len in sample_before:
            print(f"  id={art_id} summary_len={summary_len} link={link}")

        stats = enrich_database_with_full_articles(storage, limit=2)
        print(f"Enrichment run stats: {stats}")

        # Fetch again for after state
        with storage.session_scope() as session:
            id_values = tuple(a[0] for a in sample_before)
            rows = session.execute(
                select(ArticleModel.id, func.length(ArticleModel.full_content).label("full_len"))
                .where(ArticleModel.id.in_(id_values))
            ).all()
            after_map = {row.id: row.full_len for row in rows}
        print("After enrichment:")
        for art_id, link, summary_len in sample_before:
            full_len = after_map.get(art_id)
            print(f"  id={art_id} full_len={full_len} link={link}")
    finally:
        storage.close()


if __name__ == "__main__":  # pragma: no cover
    main()
