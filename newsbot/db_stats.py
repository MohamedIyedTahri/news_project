"""Database statistics utility.

Provides per-category coverage of full_content enrichment.

Usage (examples):
  python -m newsbot.db_stats
  python -m newsbot.db_stats --json
  python -m newsbot.db_stats --min-coverage 70

Exit codes:
  0 success
  2 if min-coverage specified and any category falls below threshold
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

DB_PATH = "news_articles.db"


@dataclass
class CategoryStat:
    category: str
    total: int
    with_full: int
    coverage_pct: float
    avg_full_length: float | None

    @property
    def missing(self) -> int:
        return self.total - self.with_full


def fetch_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category,
               COUNT(*) as total,
               SUM(CASE WHEN full_content IS NOT NULL AND length(trim(full_content))>0 THEN 1 ELSE 0 END) as with_full,
               AVG(CASE WHEN full_content IS NOT NULL AND length(trim(full_content))>0 THEN length(full_content) END) as avg_len_full
        FROM articles
        GROUP BY category
        ORDER BY total DESC
        """
    )
    rows = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*), SUM(CASE WHEN full_content IS NOT NULL AND length(trim(full_content))>0 THEN 1 ELSE 0 END) FROM articles"
    )
    all_total, all_full = cur.fetchone()
    conn.close()

    categories: List[CategoryStat] = []
    for cat, total, with_full, avg_len in rows:
        coverage = (with_full / total * 100) if total else 0.0
        categories.append(
            CategoryStat(
                category=cat or "(uncategorized)",
                total=total,
                with_full=with_full or 0,
                coverage_pct=round(coverage, 2),
                avg_full_length=round(avg_len, 1) if avg_len is not None else None,
            )
        )

    overall_cov = (all_full / all_total * 100) if all_total else 0.0
    return {
        "overall": {
            "total": all_total,
            "with_full": all_full,
            "coverage_pct": round(overall_cov, 2),
        },
        "categories": [asdict(c) for c in categories],
    }


def format_table(stats: Dict[str, Any]) -> str:
    lines: List[str] = []
    overall = stats["overall"]
    lines.append(
        f"Overall coverage: {overall['with_full']}/{overall['total']} ({overall['coverage_pct']:.2f}%)"
    )
    lines.append("".ljust(78, "-"))
    lines.append(
        f"{'Category':15s} {'Total':>7s} {'Full':>7s} {'Miss':>7s} {'Cover%':>8s} {'AvgFullLen':>11s}"
    )
    lines.append("".ljust(78, "-"))
    for c in stats["categories"]:
        lines.append(
            f"{c['category'][:15]:15s} {c['total']:7d} {c['with_full']:7d} {c['total']-c['with_full']:7d} {c['coverage_pct']:8.2f} {str(c['avg_full_length'] or '-'):>11s}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print per-category full_content coverage stats")
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database (default: news_articles.db)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    parser.add_argument(
        "--min-coverage",
        type=float,
        help="If provided, exit with code 2 if any category coverage_pct < threshold",
    )
    args = parser.parse_args()

    stats = fetch_stats(args.db)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_table(stats))

    if args.min_coverage is not None:
        below = [c for c in stats["categories"] if c["coverage_pct"] < args.min_coverage]
        if below:
            print("\nCategories below threshold:")
            for c in below:
                print(f" - {c['category']}: {c['coverage_pct']}%")
            return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
