"""Kafka RSS Producer

Fetches RSS articles using existing fetch_multiple_feeds pipeline and publishes
summary-level article records to the 'rss.items' Kafka topic.

Supports two run modes:
  --once          Produce a single batch then exit.
  --poll N        Loop forever sleeping N minutes between fetches.

Environment Variables:
  KAFKA_BOOTSTRAP_SERVERS  (default: localhost:9092)
  RSS_PRODUCER_TOPIC       (default: rss.items)
  PRODUCER_CATEGORIES      Comma-separated subset of categories (default: all)
  PRODUCER_SLEEP_JITTER_S  Extra random jitter seconds added between loops (default: 20)
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import time
from typing import Dict, List

from newsbot.main import fetch_multiple_feeds
from .kafka_utils import (
    build_producer, to_json, now_iso, gen_uuid, PRODUCER_METRICS,
    flush_producer, ShutdownFlag, install_signal_handlers, log_metrics
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_TOPIC = os.environ.get("RSS_PRODUCER_TOPIC", "rss.items")


def _flatten_articles(articles_by_cat: Dict[str, List[Dict]]) -> List[Dict]:
    flat = []
    for cat, lst in articles_by_cat.items():
        for a in lst:
            flat.append(a)
    return flat


def build_message(article: Dict) -> Dict:
    return {
        "id": gen_uuid(),
        "title": article.get("title", ""),
        "link": article.get("link", ""),
        "publish_date": article.get("publish_date") or "",
        "source": article.get("source", "Unknown"),
        "category": article.get("category", "uncategorized"),
        "summary": article.get("content", ""),
        "fetched_at": now_iso(),
    }


def produce_batch(producer, topic: str, categories=None) -> int:  # type: ignore
    articles_by_cat = fetch_multiple_feeds(categories, use_deduplication=True)
    flat = _flatten_articles(articles_by_cat)
    logger.info(f"Producing {len(flat)} RSS articles to topic={topic}")
    produced = 0
    for art in flat:
        msg = build_message(art)
        try:
            producer.produce(
                topic=topic,
                key=msg["link"].encode("utf-8"),
                value=to_json(msg),
                on_delivery=lambda err, record, mid=msg["id"]: _delivery_cb(err, record, mid)
            )
            produced += 1
            PRODUCER_METRICS["messages_produced"] += 1
        except BufferError:
            # local buffer full, flush then retry once
            logger.warning("Producer buffer full; flushing")
            flush_producer(producer)
            try:
                producer.produce(topic=topic, key=msg["link"].encode("utf-8"), value=to_json(msg))
                produced += 1
                PRODUCER_METRICS["messages_produced"] += 1
            except Exception as e:
                PRODUCER_METRICS["produce_errors"] += 1
                logger.error(f"Failed to produce after flush: {e}")
        except Exception as e:
            PRODUCER_METRICS["produce_errors"] += 1
            logger.error(f"Produce error: {e}")
    flush_producer(producer)
    log_metrics()
    return produced


def _delivery_cb(err, record, mid):  # type: ignore
    if err:
        logger.error(f"Delivery failed id={mid} err={err}")
    else:
        logger.debug(f"Delivered id={mid} partition={record.partition()} offset={record.offset()}")


def main():
    parser = argparse.ArgumentParser(description="Kafka RSS Producer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--once', action='store_true', help='Produce a single batch then exit')
    group.add_argument('--poll', type=int, metavar='MINUTES', help='Continuously poll every N minutes')
    parser.add_argument('--categories', type=str, help='Comma-separated categories subset')
    parser.add_argument('--topic', type=str, default=DEFAULT_TOPIC, help='Target Kafka topic')
    parser.add_argument('--sleep-jitter-max', type=int, default=int(os.environ.get('PRODUCER_SLEEP_JITTER_S', '20')),
                        help='Max random extra seconds added to poll interval')
    args = parser.parse_args()

    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(',') if c.strip()]

    producer = build_producer()

    if args.once:
        produce_batch(producer, args.topic, categories)
        return

    # Polling mode
    interval_minutes = args.poll
    flag = ShutdownFlag()
    install_signal_handlers(flag)

    logger.info(f"Starting polling producer interval={interval_minutes}m topic={args.topic}")
    while not flag.triggered:
        start = time.time()
        try:
            count = produce_batch(producer, args.topic, categories)
            elapsed = time.time() - start
            logger.info(f"Produced batch size={count} elapsed={elapsed:.1f}s")
        except Exception as e:
            logger.error(f"Batch production error: {e}")
        # Sleep until next iteration
        if flag.triggered:
            break
        sleep_base = interval_minutes * 60
        jitter = random.uniform(0, args.sleep_jitter_max)
        total_sleep = sleep_base + jitter
        logger.info(f"Sleeping {total_sleep:.1f}s before next batch")
        for _ in range(int(total_sleep)):
            if flag.triggered:
                break
            time.sleep(1)

    logger.info("Producer shutdown complete.")

if __name__ == '__main__':
    main()
