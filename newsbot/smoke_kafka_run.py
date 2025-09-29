"""Manual smoke script for Kafka streaming layer.

Usage:
  python -m newsbot.smoke_kafka_run

Sequence:
  1. Produce a single batch of RSS items (subset categories optional via env PRODUCER_CATEGORIES)
  2. Run sync consumer for a limited number of messages (default 5)
  3. Print DB stats and exit.

Kafka must be running and topics created.
"""
from __future__ import annotations

import os
import subprocess
import sys

MAX_MESSAGES = int(os.environ.get("SMOKE_MAX_MESSAGES", "5"))
CATEGORIES = os.environ.get("PRODUCER_CATEGORIES")


def run(cmd: list[str]):
    print("\n>>", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"Command failed rc={result.returncode}")
        sys.exit(result.returncode)


def main():
    base = [sys.executable, '-m']
    prod_cmd = base + ['newsbot.kafka_producer', '--once']
    if CATEGORIES:
        prod_cmd += ['--categories', CATEGORIES]
    run(prod_cmd)

    cons_cmd = base + ['newsbot.kafka_scraper_consumer', '--max-messages', str(MAX_MESSAGES)]
    run(cons_cmd)

    # Print simple DB stats using storage class
    from .storage import NewsStorage
    s = NewsStorage()
    stats = s.get_statistics()
    print("\nDB Stats after smoke run:")
    print(stats)
    s.close()

if __name__ == '__main__':
    main()
