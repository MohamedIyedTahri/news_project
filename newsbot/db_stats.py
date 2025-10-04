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
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, select

from .db import get_session_factory
from .models import Article


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
def fetch_stats(database_url: Optional[str] = None) -> Dict[str, Any]:
    session_factory = get_session_factory(database_url)
    full_case = case(
        (func.length(func.trim(Article.full_content)) > 0, 1),
        else_=0,
    )

    categories: List[CategoryStat] = []
    with session_factory() as session:
        category_rows = session.execute(
            select(
                Article.category,
                func.count(Article.id),
                func.sum(full_case),
                func.avg(func.nullif(func.length(func.trim(Article.full_content)), 0)),
            )
            .group_by(Article.category)
            .order_by(func.count(Article.id).desc())
        ).all()

        overall_row = session.execute(
            select(
                func.count(Article.id),
                func.sum(full_case),
            )
        ).one()

    for cat, total, with_full, avg_len in category_rows:
        total = int(total or 0)
        with_full = int(with_full or 0)
        coverage = (with_full / total * 100) if total else 0.0
        categories.append(
            CategoryStat(
                category=cat or "(uncategorized)",
                total=total,
                with_full=with_full,
                coverage_pct=round(coverage, 2),
                avg_full_length=round(avg_len, 1) if avg_len is not None else None,
            )
        )

    all_total = int(overall_row[0] or 0)
    all_full = int(overall_row[1] or 0)
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
    parser.add_argument("--database-url", help="Optional override for SQLAlchemy database URL")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    parser.add_argument(
        "--min-coverage",
        type=float,
        help="If provided, exit with code 2 if any category coverage_pct < threshold",
    )
    args = parser.parse_args()

    stats = fetch_stats(args.database_url)
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
