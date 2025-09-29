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

from newsbot.storage import NewsStorage
from newsbot.main import enrich_database_with_full_articles

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _fetch_sample_missing(storage: NewsStorage, limit: int = 2) -> List[Tuple[int, str, int]]:
    cur = storage.conn.execute(
        """
        SELECT id, link, length(COALESCE(content,'')) as summary_len
        FROM articles
        WHERE (full_content IS NULL OR length(full_content)=0)
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [(r[0], r[1], r[2]) for r in cur.fetchall()]


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
        cur = storage.conn.execute(
            "SELECT id, length(full_content) FROM articles WHERE id IN (?,?)",
            tuple(a[0] for a in sample_before) if len(sample_before) == 2 else (sample_before[0][0], -1),
        )
        after_map = {row[0]: row[1] for row in cur.fetchall()}
        print("After enrichment:")
        for art_id, link, summary_len in sample_before:
            full_len = after_map.get(art_id)
            print(f"  id={art_id} full_len={full_len} link={link}")
    finally:
        storage.close()


if __name__ == "__main__":  # pragma: no cover
    main()
